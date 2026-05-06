"""
TimelineWidget — custom-painted interactive timeline.

Features
--------
- Ruler with dynamic time labels (adapts to zoom level)
- Coloured clip blocks (gradient, rounded corners)
- Draggable playhead
- Click on clip → select; drag clip edges → trim; drag clip body → move
- Ctrl+Scroll to zoom in/out
- Right-click context menu on clips
- Selected clips show gold border + glow
- Overlapping clips shown in amber/warning style
- Exported clips shown in green
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    Qt, QRect, QRectF, QPointF, QTimer, Signal, QObject,
)
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QFont, QFontMetrics, QPainterPath, QCursor,
)
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QSizePolicy, QMenu,
    QAbstractScrollArea,
)

from god_factory_editor.core.clip_manager import ClipManager
from god_factory_editor.utils.time_utils import seconds_to_str
from god_factory_editor.config import COLOURS
from god_factory_editor.utils.thumbnail_gen import ThumbnailGenerator


# ── Colours ───────────────────────────────────────────────────────────────────
_C = {
    "bg":           QColor(COLOURS["bg_surface"]),
    "ruler_bg":     QColor(COLOURS["bg_elevated"]),
    "ruler_text":   QColor(COLOURS["text_secondary"]),
    "grid":         QColor(COLOURS["border"]),
    "clip":         QColor(COLOURS["clip_normal"]),
    "clip_sel":     QColor(COLOURS["clip_selected"]),
    "clip_exp":     QColor(COLOURS["clip_exported"]),
    "clip_fail":    QColor(COLOURS["clip_failed"]),
    "clip_overlap": QColor(COLOURS["warning"]),
    "playhead":     QColor(COLOURS["playhead"]),
    "text":         QColor(COLOURS["text_primary"]),
}

RULER_H = 28
TRACK_H = 60
EDGE_GRAB = 8    # pixels from clip edge that trigger resize cursor


class TimelineWidget(QWidget):
    """
    Signals
    -------
    seek_requested(seconds)
    clip_selected(clip_id)
    clip_double_clicked(clip_id)
    clip_context_menu(clip_id, global_pos)
    """

    seek_requested = Signal(float)
    clip_selected = Signal(str)
    clip_double_clicked = Signal(str)
    clip_context_menu = Signal(str, object)

    def __init__(self, clip_manager: ClipManager, parent=None):
        super().__init__(parent)
        self._cm = clip_manager
        self._duration: float = 0.0
        self._zoom: float = 10.0          # pixels per second
        self._playhead: float = 0.0
        self._in_point: Optional[float] = None
        self._out_point: Optional[float] = None
        self._source_label: str = "Loaded Video"
        self._source_path: Optional[Path] = None
        self._thumb_gen = ThumbnailGenerator(self)
        self._thumb_gen.thumbnail_ready.connect(self._on_thumb_ready)
        self._thumb_cache: dict[str, object] = {}
        self._thumb_pending: set[str] = set()

        # Drag state
        self._drag_mode: str = "none"     # none | playhead | move | resize_l | resize_r
        self._drag_clip_id: Optional[str] = None
        self._drag_start_x: int = 0
        self._drag_clip_orig_start: float = 0.0
        self._drag_clip_orig_end: float = 0.0

        self.setMinimumHeight(RULER_H + TRACK_H + 8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)

        self._cm.clips_changed.connect(self.update)

    # ── Public ────────────────────────────────────────────────────────────────
    def set_duration(self, seconds: float):
        self._duration = seconds
        self._update_width()
        self.update()

    def set_playhead(self, seconds: float):
        self._playhead = seconds
        self.update()
        self._auto_scroll()

    def set_in_point(self, seconds: Optional[float]):
        self._in_point = seconds
        self.update()

    def set_out_point(self, seconds: Optional[float]):
        self._out_point = seconds
        self.update()

    def clear_in_out(self):
        """Compatibility helper used by main window after creating a clip."""
        self._in_point = None
        self._out_point = None
        self.update()

    def set_zoom(self, pixels_per_second: float):
        self._zoom = max(0.5, min(pixels_per_second, 500.0))
        self._update_width()
        self.update()

    def zoom_in(self):
        self.set_zoom(self._zoom * 1.5)

    def zoom_out(self):
        self.set_zoom(self._zoom / 1.5)

    def fit_to_width(self):
        w = self.parent().width() if self.parent() else self.width()
        if self._duration > 0:
            self.set_zoom((w - 20) / self._duration)

    def fit_to_window(self):
        """Compatibility alias used by the main window action."""
        self.fit_to_width()

    def set_source_label(self, label: str):
        self._source_label = label or "Loaded Video"
        self.update()

    def set_source_path(self, path: Optional[Path]):
        self._source_path = Path(path) if path else None
        self._thumb_cache.clear()
        self._thumb_pending.clear()
        self.update()

    # ── Coordinate helpers ────────────────────────────────────────────────────
    def _x_to_seconds(self, x: int) -> float:
        return x / self._zoom

    def _seconds_to_x(self, s: float) -> int:
        return int(s * self._zoom)

    def _clip_rect(self, clip) -> QRect:
        x1 = self._seconds_to_x(clip.start_time)
        x2 = self._seconds_to_x(clip.end_time)
        return QRect(x1, RULER_H + 4, max(x2 - x1, 4), TRACK_H - 8)

    def _hit_clip(self, x: int, y: int) -> Optional[str]:
        if y < RULER_H:
            return None
        for clip in reversed(self._cm.clips):
            r = self._clip_rect(clip)
            if r.contains(x, y):
                return clip.id
        return None

    def _hit_edge(self, clip_id: str, x: int) -> Optional[str]:
        clip = self._cm.get_by_id(clip_id)
        if clip is None:
            return None
        r = self._clip_rect(clip)
        if abs(x - r.left()) <= EDGE_GRAB:
            return "left"
        if abs(x - r.right()) <= EDGE_GRAB:
            return "right"
        return None

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._duration <= 0:
            self._draw_background(p)
            self._draw_empty_state(
                p,
                "Load a video to see the full timeline here."
            )
            return

        self._draw_background(p)
        self._draw_ruler(p)
        self._draw_source_track(p)
        self._draw_in_out(p)
        self._draw_clips(p)
        self._draw_playhead(p)

        if not self._cm.clips:
            self._draw_empty_state(
                p,
                "No clips yet. Press I to mark a start, then O to create a clip."
            )

    def _draw_background(self, p: QPainter):
        p.fillRect(self.rect(), _C["bg"])
        p.fillRect(0, 0, self.width(), RULER_H, _C["ruler_bg"])

        # Vertical grid lines (every 60s or adapted interval)
        p.setPen(QPen(_C["grid"], 1, Qt.DotLine))
        interval = self._grid_interval()
        t = 0.0
        while t <= self._duration:
            x = self._seconds_to_x(t)
            p.drawLine(x, RULER_H, x, self.height())
            t += interval

    def _draw_ruler(self, p: QPainter):
        font = QFont("Segoe UI", 9)
        p.setFont(font)
        p.setPen(_C["ruler_text"])

        interval = self._grid_interval()
        t = 0.0
        while t <= self._duration:
            x = self._seconds_to_x(t)
            label = seconds_to_str(t)
            fm = QFontMetrics(font)
            tw = fm.horizontalAdvance(label)
            p.drawText(x - tw // 2, RULER_H - 6, label)
            # tick
            p.setPen(QPen(_C["grid"], 1))
            p.drawLine(x, RULER_H - 5, x, RULER_H)
            p.setPen(_C["ruler_text"])
            t += interval

    def _draw_in_out(self, p: QPainter):
        """Draw in-point (green) and out-point (red) markers."""
        if self._in_point is not None:
            x = self._seconds_to_x(self._in_point)
            p.setPen(QPen(QColor("#3fb950"), 2))
            p.drawLine(x, RULER_H, x, self.height())
            p.fillRect(x - 4, RULER_H, 8, 10, QColor("#3fb950"))

        if self._out_point is not None:
            x = self._seconds_to_x(self._out_point)
            p.setPen(QPen(QColor("#f85149"), 2))
            p.drawLine(x, RULER_H, x, self.height())
            p.fillRect(x - 4, RULER_H, 8, 10, QColor("#f85149"))

    def _draw_source_track(self, p: QPainter):
        track_rect = QRect(0, RULER_H + 6, max(self.width() - 1, 1), TRACK_H - 12)
        grad = QLinearGradient(track_rect.topLeft(), track_rect.bottomLeft())
        grad.setColorAt(0, QColor("#30451f"))
        grad.setColorAt(1, QColor("#1d2a14"))
        path = QPainterPath()
        path.addRoundedRect(QRectF(track_rect), 5, 5)
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(QColor("#556b2f"), 1))
        p.drawPath(path)

        # Draw source video frames if available
        if self._source_path and self._source_path.exists() and self._duration > 0:
            frame_h = track_rect.height()
            frame_w = int(frame_h * 16 / 9)  # Assume 16:9 aspect ratio
            
            # Calculate frame interval: one frame every 1-2 seconds to avoid overcrowding
            frame_interval = max(1.0, self._duration / 20)  # Show ~20 frames
            
            t = 0.0
            x = track_rect.left()
            frame_idx = 0
            while t <= self._duration and x < track_rect.right():
                frame_id = f"source_{frame_idx}"
                
                # Request thumbnail if not already cached
                if frame_id not in self._thumb_cache and frame_id not in self._thumb_pending:
                    self._thumb_pending.add(frame_id)
                    self._thumb_gen.request(frame_id, self._source_path, t, frame_w, frame_h)
                
                # Draw cached thumbnail if available
                if frame_id in self._thumb_cache:
                    thumb = self._thumb_cache[frame_id]
                    if thumb and not thumb.isNull():
                        frame_rect = QRect(x, track_rect.top(), frame_w, frame_h)
                        p.drawPixmap(frame_rect, thumb)
                        p.setPen(QPen(QColor("#556b2f"), 1))
                        p.drawRect(frame_rect)
                
                x += frame_w
                t += frame_interval
                frame_idx += 1
        
        # Draw label overlay
        p.setPen(QColor("#d8e2c8"))
        font = QFont("Segoe UI", 9)
        font.setBold(True)
        p.setFont(font)
        p.drawText(track_rect.adjusted(10, 0, -10, 0), Qt.AlignLeft | Qt.AlignVCenter, self._source_label)

    def _draw_clips(self, p: QPainter):
        overlapping = {cid for pair in self._cm.overlapping_pairs() for cid in pair}

        for clip in self._cm.clips:
            r = self._clip_rect(clip)
            selected = self._cm.is_selected(clip.id)

            # Choose base colour
            if clip.id in overlapping:
                base = _C["clip_overlap"]
            elif clip.export_status == "exported":
                base = _C["clip_exp"]
            elif clip.export_status == "failed":
                base = _C["clip_fail"]
            else:
                base = _C["clip_sel"] if selected else _C["clip"]

            # Gradient fill
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, base.lighter(120))
            grad.setColorAt(1, base.darker(110))
            path = QPainterPath()
            path.addRoundedRect(QRectF(r), 4, 4)
            p.fillPath(path, QBrush(grad))

            # Border
            if selected:
                p.setPen(QPen(_C["clip_sel"], 2))
            else:
                p.setPen(QPen(base.darker(130), 1))
            p.drawPath(path)

            # Label
            if r.width() > 30:
                self._draw_clip_frames(p, clip, r)
                p.setPen(_C["text"])
                font = QFont("Segoe UI", 8)
                font.setBold(selected)
                p.setFont(font)
                label = clip.name or f"{clip.start_str}→{clip.end_str}"
                p.drawText(
                    r.adjusted(6, 4, -6, -4),
                    Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine,
                    label,
                )

    def _draw_clip_frames(self, p: QPainter, clip, clip_rect: QRect):
        if self._source_path is None or clip_rect.width() < 60 or clip_rect.height() < 28:
            return

        slot_w = 38
        gap = 4
        max_slots = max(1, (clip_rect.width() - 8) // (slot_w + gap))
        slots = min(6, max_slots)
        if slots <= 0:
            return

        for i in range(slots):
            frac = (i + 0.5) / slots
            t = clip.start_time + (clip.end_time - clip.start_time) * frac
            key = self._thumb_key(clip.id, clip.start_time, clip.end_time, i)

            x = clip_rect.left() + 4 + i * (slot_w + gap)
            y = clip_rect.top() + 4
            h = max(14, clip_rect.height() - 8)
            frame_rect = QRect(x, y, slot_w, h)

            cached = self._thumb_cache.get(key)
            if cached is not None:
                p.drawPixmap(frame_rect, cached)
                continue

            p.fillRect(frame_rect, QColor(255, 255, 255, 24))
            if key not in self._thumb_pending:
                self._thumb_pending.add(key)
                self._thumb_gen.request(key, self._source_path, t, width=slot_w * 2, height=h * 2)

    def _thumb_key(self, clip_id: str, start: float, end: float, idx: int) -> str:
        digest = hashlib.md5(f"{clip_id}|{start:.3f}|{end:.3f}|{idx}".encode("utf-8")).hexdigest()[:12]
        return f"tl_{digest}"

    def _on_thumb_ready(self, clip_id: str, pixmap):
        if not (clip_id.startswith("tl_") or clip_id.startswith("source_")):
            return
        self._thumb_pending.discard(clip_id)
        self._thumb_cache[clip_id] = pixmap
        self.update()

    def _draw_playhead(self, p: QPainter):
        x = self._seconds_to_x(self._playhead)
        p.setPen(QPen(_C["playhead"], 2))
        p.drawLine(x, 0, x, self.height())
        # Diamond head
        head = QRectF(x - 6, 0, 12, 12)
        p.setBrush(QBrush(_C["playhead"]))
        p.setPen(Qt.NoPen)
        diamond = QPainterPath()
        diamond.moveTo(x, 0)
        diamond.lineTo(x + 6, 6)
        diamond.lineTo(x, 12)
        diamond.lineTo(x - 6, 6)
        diamond.closeSubpath()
        p.fillPath(diamond, _C["playhead"])

    def _draw_empty_state(self, p: QPainter, message: str):
        p.setPen(_C["ruler_text"])
        font = QFont("Segoe UI", 10)
        font.setItalic(True)
        p.setFont(font)
        rect = self.rect().adjusted(20, RULER_H + 8, -20, -12)
        p.drawText(rect, Qt.AlignCenter | Qt.TextWordWrap, message)

    # ── Grid interval logic ───────────────────────────────────────────────────
    def _grid_interval(self) -> float:
        """Choose a nice grid interval based on zoom."""
        candidates = [1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        px_per_candidate = [c * self._zoom for c in candidates]
        for i, px in enumerate(px_per_candidate):
            if px >= 80:
                return float(candidates[i])
        return 3600.0

    # ── Mouse ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        x, y = event.position().x(), event.position().y()
        x, y = int(x), int(y)

        if event.button() == Qt.RightButton:
            cid = self._hit_clip(x, y)
            if cid:
                self._cm.select(cid)
                self.clip_context_menu.emit(cid, event.globalPosition().toPoint())
            return

        if y < RULER_H:
            # Click on ruler → seek
            self._drag_mode = "playhead"
            sec = self._x_to_seconds(x)
            self.seek_requested.emit(max(0, min(sec, self._duration)))
            return

        cid = self._hit_clip(x, y)
        if cid:
            clip = self._cm.get_by_id(cid)
            edge = self._hit_edge(cid, x)
            self._cm.select(cid, exclusive=not (event.modifiers() & Qt.ControlModifier))
            self.clip_selected.emit(cid)
            self._drag_start_x = x
            self._drag_clip_id = cid
            self._drag_clip_orig_start = clip.start_time
            self._drag_clip_orig_end = clip.end_time
            if edge == "left":
                self._drag_mode = "resize_l"
            elif edge == "right":
                self._drag_mode = "resize_r"
            else:
                self._drag_mode = "move"
        else:
            self._cm.deselect_all()
            self._drag_mode = "seek"
            sec = self._x_to_seconds(x)
            self.seek_requested.emit(max(0, min(sec, self._duration)))

    def mouseMoveEvent(self, event):
        x = int(event.position().x())
        y = int(event.position().y())

        # Cursor hint
        cid = self._hit_clip(x, y)
        if cid and y >= RULER_H:
            edge = self._hit_edge(cid, x)
            if edge:
                self.setCursor(Qt.SizeHorCursor)
            else:
                self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if self._drag_mode == "none":
            return

        delta_px = x - self._drag_start_x
        delta_sec = delta_px / self._zoom

        if self._drag_mode in ("playhead", "seek"):
            sec = self._x_to_seconds(x)
            self.seek_requested.emit(max(0, min(sec, self._duration)))

        elif self._drag_mode == "move" and self._drag_clip_id:
            new_start = max(0.0, self._drag_clip_orig_start + delta_sec)
            dur = self._drag_clip_orig_end - self._drag_clip_orig_start
            new_end = min(self._duration, new_start + dur)
            new_start = new_end - dur
            self._cm.update_clip(
                self._drag_clip_id,
                start_time=new_start,
                end_time=new_end,
            )

        elif self._drag_mode == "resize_l" and self._drag_clip_id:
            new_start = max(0.0, self._drag_clip_orig_start + delta_sec)
            new_start = min(new_start, self._drag_clip_orig_end - 0.5)
            self._cm.update_clip(self._drag_clip_id, start_time=new_start)

        elif self._drag_mode == "resize_r" and self._drag_clip_id:
            new_end = min(self._duration, self._drag_clip_orig_end + delta_sec)
            new_end = max(new_end, self._drag_clip_orig_start + 0.5)
            self._cm.update_clip(self._drag_clip_id, end_time=new_end)

    def mouseReleaseEvent(self, event):
        self._drag_mode = "none"
        self._drag_clip_id = None

    def mouseDoubleClickEvent(self, event):
        x, y = int(event.position().x()), int(event.position().y())
        cid = self._hit_clip(x, y)
        if cid:
            self.clip_double_clicked.emit(cid)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _update_width(self):
        w = max(200, self._seconds_to_x(self._duration) + 40)
        self.setMinimumWidth(w)
        self.resize(w, self.height())

    def _auto_scroll(self):
        """If the playhead is near the edge, scroll the parent scroll area."""
        scroll = self._find_scroll_area()
        if scroll is None:
            return
        ph_x = self._seconds_to_x(self._playhead)
        sb = scroll.horizontalScrollBar()
        view_left = sb.value()
        view_right = view_left + scroll.viewport().width()
        margin = 80
        if ph_x > view_right - margin:
            sb.setValue(min(sb.maximum(), ph_x - scroll.viewport().width() // 2))
        elif ph_x < view_left + margin:
            sb.setValue(max(0, ph_x - margin))

    def _find_scroll_area(self) -> Optional[QScrollArea]:
        p = self.parent()
        while p:
            if isinstance(p, QScrollArea):
                return p
            p = p.parent()
        return None
