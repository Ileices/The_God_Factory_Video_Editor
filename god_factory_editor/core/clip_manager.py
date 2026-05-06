"""
ClipManager — authoritative source of truth for all clips.
Emits Qt signals whenever the clip list changes so the UI can stay in sync.
Provides full undo/redo via a snapshot stack.
"""

from __future__ import annotations
import copy
from typing import List, Optional, Set, Tuple, Union

from PySide6.QtCore import QObject, Signal

from god_factory_editor.models.clip import Clip
from god_factory_editor.utils.logger import log


class ClipManager(QObject):

    # Emitted after any change so views can refresh
    clips_changed = Signal()
    clip_added = Signal(object)          # Clip
    clip_removed = Signal(str)           # clip id
    clip_updated = Signal(str, object)   # id, Clip
    selection_changed = Signal(list)     # list[str] ids

    MAX_UNDO = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._clips: List[Clip] = []
        self._selected: Set[str] = set()
        self._undo_stack: List[List[Clip]] = []
        self._redo_stack: List[List[Clip]] = []
        self._video_duration: float = 0.0

    # ── Setup ─────────────────────────────────────────────────────────────────
    def set_video_duration(self, duration: float):
        self._video_duration = duration

    def reset(self):
        self._clips.clear()
        self._selected.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.clips_changed.emit()

    # ── Read ──────────────────────────────────────────────────────────────────
    @property
    def clips(self) -> List[Clip]:
        return list(self._clips)

    @property
    def count(self) -> int:
        return len(self._clips)

    def get_by_id(self, clip_id: str) -> Optional[Clip]:
        for c in self._clips:
            if c.id == clip_id:
                return c
        return None

    def get_index(self, clip_id: str) -> int:
        for i, c in enumerate(self._clips):
            if c.id == clip_id:
                return i
        return -1

    def selected_clips(self) -> List[Clip]:
        return [c for c in self._clips if c.id in self._selected]

    @property
    def selected_clip_ids(self) -> List[str]:
        """Compatibility alias used by some UI components."""
        return list(self._selected)

    def get_clip(self, clip_id: str) -> Optional[Clip]:
        """Compatibility alias used by main window/actions."""
        return self.get_by_id(clip_id)

    # ── Selection ─────────────────────────────────────────────────────────────
    def select(self, clip_id: str, exclusive: bool = True):
        if exclusive:
            self._selected = {clip_id} if clip_id else set()
        else:
            self._selected.add(clip_id)
        self.selection_changed.emit(list(self._selected))

    def deselect_all(self):
        self._selected.clear()
        self.selection_changed.emit([])

    def select_all(self):
        self._selected = {c.id for c in self._clips}
        self.selection_changed.emit(list(self._selected))

    def is_selected(self, clip_id: str) -> bool:
        return clip_id in self._selected

    # ── CRUD ──────────────────────────────────────────────────────────────────
    def add_clip(self,
                 start: Union[float, Clip],
                 end: Optional[float] = None,
                 name: str = "") -> Optional[Clip]:
        """
        Add a clip.

        Accepts either:
        - add_clip(start_float, end_float, name)
        - add_clip(clip_instance)
        """
        if isinstance(start, Clip):
            clip = start
        else:
            if end is None:
                log.warning("Invalid clip add request: missing 'end' time.")
                return None
            clip = Clip(start_time=start, end_time=end, name=name or "")
        ok, err = clip.validate()
        if not ok:
            log.warning(f"Invalid clip: {err}")
            return None

        # Clamp to video
        if self._video_duration > 0:
            clip.start_time = max(0.0, clip.start_time)
            clip.end_time = min(self._video_duration, clip.end_time)

        self._snapshot()
        self._clips.append(clip)
        self._clips.sort(key=lambda c: c.start_time)
        self.clips_changed.emit()
        self.clip_added.emit(clip)
        log.debug(f"Clip added: {clip.name or clip.id} [{clip.start_str} → {clip.end_str}]")
        return clip

    def remove_clip(self, clip_id: str):
        idx = self.get_index(clip_id)
        if idx < 0:
            return
        self._snapshot()
        self._clips.pop(idx)
        self._selected.discard(clip_id)
        self.clips_changed.emit()
        self.clip_removed.emit(clip_id)

    def update_clip(self, clip_id: str, **kwargs):
        clip = self.get_by_id(clip_id)
        if clip is None:
            return
        self._snapshot()
        for k, v in kwargs.items():
            if hasattr(clip, k):
                setattr(clip, k, v)
        ok, err = clip.validate()
        if not ok:
            self._undo()   # revert bad edit
            log.warning(f"Update rejected: {err}")
            return
        self._clips.sort(key=lambda c: c.start_time)
        self.clips_changed.emit()
        self.clip_updated.emit(clip_id, clip)

    def split_clip(self, clip_id: str, split_time: float) -> Tuple[Optional[Clip], Optional[Clip]]:
        """Split clip at split_time; return (left, right) or (None, None) on failure."""
        clip = self.get_by_id(clip_id)
        if clip is None:
            return None, None
        if not (clip.start_time < split_time < clip.end_time):
            return None, None

        self._snapshot()
        idx = self.get_index(clip_id)
        left = clip.copy()
        right = clip.copy()
        import uuid
        right.id = str(uuid.uuid4())
        left.end_time = split_time
        right.start_time = split_time
        right.name = clip.name + " (2)" if clip.name else ""
        left.name = clip.name + " (1)" if clip.name else ""
        self._clips[idx] = left
        self._clips.insert(idx + 1, right)
        self.clips_changed.emit()
        return left, right

    def merge_clips(self, clip_ids: List[str]) -> Optional[Clip]:
        """Merge selected clips into one spanning the full range."""
        clips = [c for c in self._clips if c.id in clip_ids]
        if len(clips) < 2:
            return None
        clips.sort(key=lambda c: c.start_time)
        self._snapshot()
        merged = clips[0].copy()
        merged.end_time = clips[-1].end_time
        merged.name = clips[0].name or "Merged Clip"
        for c in clips:
            self.remove_clip(c.id)
        self._clips.append(merged)
        self._clips.sort(key=lambda c: c.start_time)
        self.clips_changed.emit()
        return merged

    def load_clips(self, clips: List[Clip]):
        """Replace all clips (used when loading a project)."""
        self._clips = list(clips)
        self._clips.sort(key=lambda c: c.start_time)
        self._selected.clear()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.clips_changed.emit()

    # ── Undo/Redo ─────────────────────────────────────────────────────────────
    def _snapshot(self):
        snapshot = [c.copy() for c in self._clips]
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self.MAX_UNDO:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _undo(self):
        if self._undo_stack:
            self._redo_stack.append([c.copy() for c in self._clips])
            self._clips = self._undo_stack.pop()
            self.clips_changed.emit()

    def undo(self):
        self._undo()

    def redo(self):
        if self._redo_stack:
            self._undo_stack.append([c.copy() for c in self._clips])
            self._clips = self._redo_stack.pop()
            self.clips_changed.emit()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    # ── Overlap detection ─────────────────────────────────────────────────────
    def overlapping_pairs(self) -> List[Tuple[str, str]]:
        pairs = []
        sorted_clips = sorted(self._clips, key=lambda c: c.start_time)
        for i in range(len(sorted_clips) - 1):
            a, b = sorted_clips[i], sorted_clips[i + 1]
            if a.end_time > b.start_time:
                pairs.append((a.id, b.id))
        return pairs
