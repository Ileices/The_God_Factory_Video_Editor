"""
HelpWindow — full in-app help system.
- Searchable topics sidebar
- Rich HTML content pane
- Every topic addressable by anchor (e.g. help_window.show_topic("export"))
- "?" buttons throughout the app can open a specific topic
- Hyperlinks within help content navigate to other topics
"""

from __future__ import annotations
import html
import re
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QTextBrowser,
    QLineEdit, QLabel, QSplitter, QToolBar,
    QStatusBar,
)
from PySide6.QtGui import QAction, QFont

from god_factory_editor.config import APP_NAME, APP_VERSION


# ── Help content (self-contained HTML) ───────────────────────────────────────
_TOPICS: list[dict] = [
    {
        "id": "welcome",
        "title": "Welcome",
        "content": f"""
        <h2>Welcome to {APP_NAME}</h2>
        <p>This app turns your long gaming live streams into individual
        challenge highlight videos — fast and easy.</p>
        <h3>The 3-step workflow</h3>
        <ol>
          <li><b>Load</b> your stream video (drag it onto the window or use File → Open)</li>
          <li><b>Mark</b> challenge segments — press <b>I</b> for the start, <b>O</b> for the end</li>
          <li><b>Export</b> — click Export Selected for near-instant video files</li>
        </ol>
        <p>That's it! The app does the rest.</p>
        <p>➡ <a href="#loading">How to load a video</a> &nbsp;|&nbsp;
           <a href="#clips">Creating clips</a> &nbsp;|&nbsp;
           <a href="#export">Exporting</a> &nbsp;|&nbsp;
            <a href="#autoedit">Auto cut boring parts</a> &nbsp;|&nbsp;
            <a href="#automation">Automation wizard</a> &nbsp;|&nbsp;
            <a href="#decibel">Decibel and loudness scan</a> &nbsp;|&nbsp;
           <a href="#speed">Speed changes</a> &nbsp;|&nbsp;
            <a href="#audio">Audio enhancement</a> &nbsp;|&nbsp;
            <a href="#picture">Picture adjustments</a></p>
        """,
    },
    {
        "id": "loading",
        "title": "Loading a Video",
        "content": """
        <h2>Loading a Video</h2>
        <p>You can open a video in three ways:</p>
        <ul>
          <li><b>Drag &amp; drop</b> your video file directly onto the app window</li>
          <li>Click <b>File → Open Video</b> (or press <b>Ctrl+O</b>)</li>
          <li>Pick a recent file from <b>File → Recent Files</b></li>
        </ul>
        <h3>Supported formats</h3>
        <p>MP4, MKV, MOV, AVI, TS, M4V, WebM — anything recorded from OBS, ShadowPlay,
        or downloaded from YouTube.</p>

        <h3>Proxy mode (recommended for 4K)</h3>
        <p>When you load a 4K video, the app automatically creates a small 480p
        <i>proxy</i> copy in the background. The preview player uses this lighter
        copy for smooth scrubbing, but all exports are always made from the original
        high-quality file.</p>
        <p>On supported Windows hardware, playback and re-encoding prefer GPU-assisted
        decode/encode paths automatically.</p>
        <p>You can toggle proxy mode with <b>Ctrl+P</b> or from the View menu.</p>

        <h3>Project files (.gfve)</h3>
        <p>When you save your work (Ctrl+S), the app creates a <code>.gfve</code> project file.
        This remembers your clips, names, tags, and where you left off. Open it later to
        resume exactly where you stopped.</p>
        ➡ <a href="#clips">Next: Creating clips</a>
        """,
    },
    {
        "id": "clips",
        "title": "Creating Clips",
        "content": """
        <h2>Creating Clips</h2>
        <h3>Method 1: Keyboard (fastest)</h3>
        <ol>
          <li>Play the video and find where your challenge starts</li>
          <li>Press <b>I</b> — a green marker appears on the timeline</li>
          <li>Continue watching to the challenge end</li>
          <li>Press <b>O</b> — the clip is created instantly and appears in the list</li>
        </ol>

        <h3>Method 2: Timeline</h3>
        <p>Click the timeline ruler to seek to any position. You can also drag the
        red playhead. When you're at the right spot, press I or O.</p>

        <h3>Naming clips</h3>
        <p>A dialog will prompt you to name each clip. You can also rename later
        by double-clicking the name in the clip list, or pressing <b>F2</b>.</p>

        <h3>Tags &amp; difficulty</h3>
        <p>Right-click any clip in the list to add tags (like <i>win</i>, <i>no_guns</i>,
        <i>stealth</i>) and a difficulty rating (1–5 stars). Tags help you filter and
        organise clips later.</p>

        <h3>Editing clip boundaries</h3>
        <ul>
          <li><b>Drag a clip edge</b> on the timeline to trim the start/end</li>
          <li><b>Press S</b> to split a clip at the current playhead position</li>
          <li><b>Select two clips + M</b> to merge them</li>
          <li><b>Ctrl+Z</b> to undo any mistake</li>
        </ul>
        ➡ <a href="#timeline">Using the Timeline</a> &nbsp;|&nbsp;
           <a href="#export">Exporting clips</a>
        """,
    },
    {
        "id": "timeline",
        "title": "Using the Timeline",
        "content": """
        <h2>Using the Timeline</h2>
        <p>The timeline at the bottom of the screen shows your entire video as a
        horizontal strip, with your clips as coloured blocks.</p>

        <h3>Navigation</h3>
        <ul>
          <li><b>Click</b> anywhere on the ruler (top bar of the timeline) to jump there</li>
          <li><b>Drag</b> the red playhead to scrub through the video</li>
          <li><b>Left / Right arrows</b> — jump 5 seconds back/forward</li>
          <li><b>Shift + Left / Right</b> — jump 30 seconds</li>
          <li><b>Ctrl + Scroll wheel</b> — zoom in/out on the timeline</li>
          <li><b>F</b> — fit the entire video into the timeline view</li>
        </ul>

        <h3>Working with clips on the timeline</h3>
        <ul>
          <li><b>Click a clip</b> to select it (it turns gold)</li>
          <li><b>Drag a clip edge</b> to trim it</li>
          <li><b>Drag a clip body</b> to move its position</li>
          <li><b>Right-click a clip</b> for a context menu with rename, delete, loop</li>
        </ul>

        <h3>Clip colours</h3>
        <ul>
          <li>Blue — normal clip, not yet exported</li>
          <li>Gold — currently selected</li>
          <li>Green — successfully exported</li>
          <li>Red — export failed</li>
          <li>Orange — overlapping with another clip</li>
        </ul>
        ➡ <a href="#clips">Creating clips</a> &nbsp;|&nbsp;
           <a href="#export">Exporting</a>
        """,
    },
    {
        "id": "autodetect",
        "title": "Auto-Detect Scenes",
        "content": """
        <h2>Auto-Detect Scenes</h2>
        <p>Instead of manually finding every challenge, let the app scan your video
        automatically and suggest where the challenges might start and end.</p>

        <h3>How to use it</h3>
        <ol>
          <li>Load your stream video</li>
          <li>Click <b>Detection → Auto-Detect Scenes</b> (or press <b>Ctrl+D</b>)</li>
          <li>A progress dialog shows the scan progress (may take several minutes for a long video)</li>
          <li>When done, the app lists all detected scene boundaries</li>
          <li>Review them: click <b>Accept</b> to create a clip from each, or <b>Skip</b> to ignore</li>
        </ol>

        <h3>Sensitivity setting</h3>
        <p>In <b>Settings → General</b> you can adjust the detection threshold.
        A <i>lower</i> number detects more scene changes (more sensitive).
        The default is 27, which works well for gameplay footage.</p>

        <h3>What it detects</h3>
        <p>The auto-detector looks for visual scene changes — like when the game
        cuts to a menu, a loading screen, or a sudden change in environment.
        It's not perfect, but it gives you a great starting point.</p>

        <h3>Want the app to skip boring downtime automatically?</h3>
        <p>Use <b>Detection → Auto-Cut Boring Parts</b>. That tool looks for long
        silence, black/loading screens, and freeze/no-motion sections, then creates
        keep-clips for the interesting parts you probably want to export.</p>

        <h3>After detection</h3>
        <p>You'll still want to fine-tune the clip boundaries on the timeline.
        The auto-detector gets you 80% there; you finish the last 20%.</p>
        ➡ <a href="#autoedit">Auto-Cut Boring Parts</a>
        """,
    },
    {
        "id": "autoedit",
        "title": "Auto-Cut Boring Parts",
        "content": """
        <h2>Auto-Cut Boring Parts</h2>
        <p>This tool is built for long streams where a lot of runtime is dead air,
        loading, inventory sitting, or quiet downtime between actual challenge moments.</p>

        <h3>What it looks for</h3>
        <ul>
          <li><b>Long silence / no talking</b> — nobody speaking for a while</li>
          <li><b>Freeze / very low motion</b> — gameplay is mostly static</li>
          <li><b>Black screens / loading screens</b> — obvious downtime</li>
        </ul>

        <h3>How to use it</h3>
        <ol>
          <li>Load your full stream video</li>
          <li>Go to <b>Detection → Auto-Cut Boring Parts</b> (Ctrl+Shift+D)</li>
          <li>Choose a template, thresholds, and behavior mode (<b>remove</b> or <b>fast-forward</b>)</li>
          <li>Optionally enable retention rules (auto transitions + SFX + slow-mo hints)</li>
          <li>Optionally generate editable speech-region auto-captions</li>
          <li>Review the generated clips and trim any boundaries you want tighter</li>
        </ol>

        <h3>Fine-tuning controls</h3>
        <ul>
          <li><b>Silence threshold</b> — how long no speech/audio must last before it counts as boring</li>
          <li><b>No-motion threshold</b> — how long freeze/static gameplay must last</li>
          <li><b>Black/loading threshold</b> — minimum black screen length</li>
          <li><b>Behavior mode</b> — remove boring portions or keep them as fast-forward segments (2× to 64×)</li>
          <li><b>Transition min clip length</b> — only apply transitions when both clips are long enough</li>
        </ul>

        <h3>Captions workflow</h3>
        <p>Auto-captions are speech-region placeholders that you can edit per clip in
        <b>Effects → Edit Clip Effects → Captions</b>. You can tweak timing, text, font name,
        and effect style line by line.</p>

        <h3>Best use case</h3>
        <p>Use this before manual editing when you have an 8–16 hour VOD and want the
        app to remove obvious dead sections first. It won't replace judgment, but it can
        cut out a huge amount of boring downtime automatically.</p>

        ➡ <a href="#autodetect">Scene Detection</a> &nbsp;|&nbsp;
           <a href="#clips">Creating Clips</a>
        """,
    },
    {
        "id": "export",
        "title": "Exporting Clips",
        "content": """
        <h2>Exporting Clips</h2>
        <h3>Quick export</h3>
        <ol>
          <li>Check the clips you want in the clip list (checkboxes on the left)</li>
          <li>Click the <b>Export</b> button in the toolbar, or press <b>Ctrl+E</b></li>
          <li>Choose an output folder and click <b>Start Export</b></li>
          <li>Done! Your clips are individual video files in that folder.</li>
        </ol>

        <h3>Export presets</h3>
        <table border="1" cellpadding="4" style="border-collapse:collapse;">
          <tr><th>Preset</th><th>Speed</th><th>Quality</th><th>Best for</th></tr>
          <tr><td>Fast (Stream Copy)</td><td>Instant</td><td>Perfect</td><td>Most cases</td></tr>
          <tr><td>Accurate (Re-encode)</td><td>Slower</td><td>Frame-perfect cuts</td><td>When exact frame matters</td></tr>
          <tr><td>YouTube 1080p</td><td>Medium</td><td>1080p H.264</td><td>YouTube uploads</td></tr>
          <tr><td>Archive 4K</td><td>Fast</td><td>Original quality</td><td>Long-term storage</td></tr>
        </table>

        <h3>Why "Fast" is usually best</h3>
        <p>Fast mode copies the video data without re-encoding it. This means:</p>
        <ul>
          <li>A 10-minute clip from a 16-hour stream exports in under 5 seconds</li>
          <li>No quality loss — the output is identical to the original</li>
          <li>The only downside: cuts may be 1–2 frames off from your exact mark</li>
        </ul>
        <p>For gaming content this is rarely noticeable. Use "Accurate" only when exact
        frame timing matters (like reaction clips).</p>

        <h3>GPU acceleration</h3>
        <p>When available, the app prefers GPU-assisted FFmpeg encoders and hardware decode
        for preview/render work. Exact GPU usage depends on your codec, driver, FFmpeg build,
        and whether the export path is stream-copy or re-encode.</p>

        ➡ <a href="#shortcuts">Keyboard shortcuts</a>
        """,
    },
    {
        "id": "shortcuts",
        "title": "Keyboard Shortcuts",
        "content": """
        <h2>Keyboard Shortcuts</h2>
        <table border="1" cellpadding="5" style="border-collapse:collapse; width:100%;">
          <tr style="background:#21262d;"><th>Key</th><th>Action</th></tr>
          <tr><td><b>Space</b></td><td>Play / Pause</td></tr>
          <tr><td><b>I</b></td><td>Mark In — set clip start point</td></tr>
          <tr><td><b>O</b></td><td>Mark Out — set clip end point</td></tr>
          <tr><td><b>← / →</b></td><td>Jump back / forward 5 seconds</td></tr>
          <tr><td><b>Shift + ← / →</b></td><td>Jump back / forward 30 seconds</td></tr>
          <tr><td><b>S</b></td><td>Split clip at playhead</td></tr>
          <tr><td><b>Delete</b></td><td>Delete selected clip</td></tr>
          <tr><td><b>Ctrl+Z</b></td><td>Undo</td></tr>
          <tr><td><b>Ctrl+Y</b></td><td>Redo</td></tr>
          <tr><td><b>Ctrl+S</b></td><td>Save project</td></tr>
          <tr><td><b>Ctrl+O</b></td><td>Open video</td></tr>
          <tr><td><b>Ctrl+E</b></td><td>Export selected clips</td></tr>
          <tr><td><b>Ctrl+Shift+E</b></td><td>Export all clips</td></tr>
          <tr><td><b>Ctrl+D</b></td><td>Auto-detect scenes</td></tr>
          <tr><td><b>Ctrl+Shift+D</b></td><td>Auto-cut boring parts</td></tr>
          <tr><td><b>Ctrl+Alt+W</b></td><td>Open Automation Wizard</td></tr>
          <tr><td><b>Ctrl+Alt+L</b></td><td>Run Decibel / Loudness Scan</td></tr>
          <tr><td><b>Ctrl+P</b></td><td>Toggle proxy mode</td></tr>
          <tr><td><b>L</b></td><td>Loop current clip (A-B repeat)</td></tr>
          <tr><td><b>F2</b></td><td>Rename selected clip</td></tr>
          <tr><td><b>Ctrl++ / Ctrl+-</b></td><td>Zoom timeline in / out</td></tr>
          <tr><td><b>F</b></td><td>Fit timeline to window</td></tr>
          <tr><td><b>F1</b></td><td>Open Help</td></tr>
        </table>
        <p><small>You can change any shortcut in <b>Settings → Shortcuts</b>.</small></p>
        """,
    },
    {
        "id": "automation",
        "title": "Automation Wizard",
        "content": """
        <h2>Automation Wizard</h2>
        <p>The Automation Wizard turns multi-step editing work into one-click pipelines.
        Open it from <b>Automation → Automation Wizard</b> or press <b>Ctrl+Alt+W</b>.</p>

        <h3>Available one-click pipelines</h3>
        <ul>
          <li><b>Stream → Highlights (Long-form)</b>: removes downtime, ranks keep moments,
              applies retention defaults, and can auto-generate editable captions.</li>
          <li><b>Stream → Shorts Pack</b>: builds short-form candidates, trims/splits long moments,
              and tags clips as short-ready.</li>
          <li><b>Audio Cleanup On Existing Clips</b>: batch-applies voice-forward presets and
              loudness-friendly settings across your clip list.</li>
        </ul>

        <h3>Key controls</h3>
        <ul>
          <li><b>Silence / No-motion / Black thresholds</b>: defines what counts as boring.</li>
          <li><b>Minimum keep segment</b>: avoids tiny unusable fragments.</li>
          <li><b>Decibel gate (LUFS)</b>: only keep moments above loudness floor.</li>
          <li><b>Max generated clips</b>: caps result set for review speed.</li>
          <li><b>Generate auto captions</b>: creates editable speech-region captions.</li>
          <li><b>Apply retention transitions + SFX</b>: one-click pacing polish.</li>
        </ul>

        <h3>Recommended workflow</h3>
        <ol>
          <li>Run <a href="#decibel">Decibel Scan</a> first for loudness context.</li>
          <li>Open Automation Wizard and choose the target pipeline.</li>
          <li>Run with conservative thresholds first, then tighten if needed.</li>
          <li>Review generated clips, tweak in Effects, then export.</li>
        </ol>

        ➡ <a href="#decibel">Decibel Scan</a> &nbsp;|&nbsp;
           <a href="#autoedit">Auto-Cut Boring Parts</a>
        """,
    },
    {
        "id": "decibel",
        "title": "Decibel and Loudness Scan",
        "content": """
        <h2>Decibel and Loudness Scan</h2>
        <p>Use <b>Automation → Run Decibel / Loudness Scan</b> (Ctrl+Alt+L) to scan your full video
        in time windows and highlight quiet or overly hot sections.</p>

        <h3>What the scan reports</h3>
        <ul>
          <li><b>Integrated LUFS</b> for each analysis window</li>
          <li><b>True Peak (dBTP)</b> and loudness range where available</li>
          <li>Counts of <b>quiet windows</b> and <b>hot windows</b> with sample timestamps</li>
        </ul>

        <h3>Useful ranges</h3>
        <ul>
          <li><b>Below -30 LUFS</b>: usually quiet/dead sections or low-energy gameplay</li>
          <li><b>-24 to -14 LUFS</b>: common active gameplay + commentary range</li>
          <li><b>Above -12 LUFS</b>: potentially too loud/hot for comfortable playback</li>
        </ul>

        <h3>How this powers automation</h3>
        <p>The Automation Wizard can use a <b>Decibel Gate (LUFS)</b> so only energetic
        moments pass into highlight/shorts pipelines.</p>

        <h3>Tip</h3>
        <p>For long streams, start around <b>-34 LUFS</b> as a gate, then increase to
        <b>-30</b> or <b>-28</b> for more aggressive highlight filtering.</p>

        ➡ <a href="#automation">Automation Wizard</a> &nbsp;|&nbsp;
           <a href="#audio">Audio Enhancement</a>
        """,
    },
    {
        "id": "tips",
        "title": "Tips & Tricks",
        "content": """
        <h2>Tips &amp; Tricks</h2>

        <h3>Working with very long streams</h3>
        <ul>
          <li>Enable <b>Proxy Mode</b> (Ctrl+P) — the app creates a small preview file
              so scrubbing is smooth even for 4K streams</li>
          <li>Use <b>Auto-Detect</b> first to get rough markers, then fine-tune manually</li>
          <li>Zoom the timeline to the section you're working on (Ctrl+Scroll)</li>
        </ul>

        <h3>Naming workflow</h3>
        <p>Name your clips immediately when you create them — it's much faster than
        going back and naming them all later. Use a consistent format like
        <code>Challenge 01 - No Guns Win</code>.</p>

        <h3>Tags</h3>
        <p>Add tags like <code>win</code>, <code>loss</code>, <code>no_guns</code>,
        <code>melee_only</code> to your clips. Then use the filter box in the clip list
        to quickly find all your wins, or all your stealth clips.</p>

        <h3>Loop preview</h3>
        <p>Press <b>L</b> on a selected clip to loop it continuously. Great for
        checking your in/out points are exactly right before exporting.</p>

        <h3>Recovering from a crash</h3>
        <p>The app auto-saves your project every 30 seconds. If it ever crashes,
        restart it and you'll be asked: <i>"Recover your last session?"</i> — click Yes.</p>

        <h3>Exporting to YouTube</h3>
        <p>Use the <b>YouTube 1080p</b> export preset. It resizes your 4K video to
        1080p and uses settings that YouTube's encoder handles most efficiently,
        giving you the best looking upload.</p>
        ➡ <a href="#export">Full export guide</a>
        """,
    },
    {
        "id": "troubleshoot",
        "title": "Troubleshooting",
        "content": """
        <h2>Troubleshooting</h2>

        <h3>Video won't play</h3>
        <ul>
          <li>Make sure the video file still exists at the same location</li>
          <li>Try enabling Proxy Mode (Ctrl+P) — sometimes the original codec
              isn't supported by the built-in player, but the proxy always works</li>
          <li>Check that Windows Media Player can play the file; if it can't,
              install <a href="https://www.codecguide.com/download_kl.htm">K-Lite Codec Pack</a></li>
        </ul>

        <h3>FFmpeg errors during export</h3>
        <ul>
          <li>Run <b>setup.bat</b> again — it will re-download FFmpeg</li>
          <li>Check <b>Settings → Tools &amp; FFmpeg</b> and click "Test FFmpeg"</li>
          <li>Check the log file in <code>%APPDATA%\\GodFactoryEditor\\logs\\</code></li>
        </ul>

        <h3>Export is slow</h3>
        <ul>
          <li>Make sure you're using the <b>Fast (Stream Copy)</b> preset — it should be instant</li>
          <li>If you're using Accurate mode, that's expected — re-encoding 4K takes time</li>
          <li>Speed changes and audio enhancement require re-encoding — this takes longer</li>
        </ul>

        <h3>Scene detection takes too long</h3>
        <ul>
          <li>This is normal for 8+ hour videos — it can take 5–20 minutes</li>
          <li>You can cancel it at any time; partial results are saved</li>
          <li>Run it overnight if you're not in a hurry</li>
        </ul>

        <h3>App crashes</h3>
        <ul>
          <li>Check the log file: <code>%APPDATA%\\GodFactoryEditor\\logs\\</code></li>
          <li>Your work is auto-saved every 30 seconds, so you won't lose much</li>
          <li>Re-run <b>setup.bat</b> to repair the installation</li>
        </ul>

        ➡ <a href="#welcome">Back to Welcome</a>
        """,
    },
    {
        "id": "speed",
        "title": "Speed Changes",
        "content": """
        <h2>Speed Changes</h2>
        <p>Change a clip's playback speed — from super slow-motion to ultra-lapse.
        This is great for skipping through setup phases at 8× or 16× while
        keeping the actual challenge moment at normal speed.</p>

        <h3>How to change speed</h3>
        <ol>
          <li>Select a clip on the timeline or clip list</li>
          <li>Press <b>E</b> to open Effects, or go to <b>Effects → Edit Clip Effects</b></li>
          <li>Click the <b>Speed</b> tab</li>
          <li>Pick a preset (0.25× to 32×) or enter a custom value</li>
          <li>The output duration preview updates instantly so you can see how long the clip will be</li>
          <li>Click OK</li>
        </ol>

        <h3>Speed presets</h3>
        <table border="1" cellpadding="5" style="border-collapse:collapse; width:100%;">
          <tr style="background:#21262d;"><th>Speed</th><th>Use case</th><th>Audio</th></tr>
          <tr><td>0.25×</td><td>Dramatic slow-mo highlight</td><td>Slowed (pitched down)</td></tr>
          <tr><td>0.5×</td><td>Slow-mo action moment</td><td>Slowed</td></tr>
          <tr><td>1×</td><td>Normal</td><td>Normal</td></tr>
          <tr><td>2×</td><td>Quick rundown, skip setup</td><td>Sped up (intelligible)</td></tr>
          <tr><td>4–8×</td><td>Timelapse between challenges</td><td>Silent (too fast)</td></tr>
          <tr><td>16–32×</td><td>1-hour lapse to 2 minutes</td><td>Silent</td></tr>
        </table>

        <h3>Important notes</h3>
        <ul>
          <li>Speed changes require re-encoding (cannot stream-copy) — expect longer export time</li>
          <li>At 4× and above, audio becomes unintelligible; the app preserves it but you may
              want to mute those segments or add SFX instead</li>
          <li>Slow-mo looks best on high-framerate (60fps+) source footage</li>
        </ul>
        ➡ <a href="#transitions">Transitions</a> &nbsp;|&nbsp;
           <a href="#sfx">Sound Effects</a>
        """,
    },
    {
        "id": "transitions",
        "title": "Transitions",
        "content": """
        <h2>Transitions</h2>
        <p>Transitions are visual effects that play <i>between</i> two clips when
        they are exported together as a single video. They replace a hard jump-cut
        with a smooth blend, wipe, or fade.</p>

        <h3>Available transitions</h3>
        <ul>
          <li><b>None (hard cut)</b> — instant jump, no effect</li>
          <li><b>Fade</b> — smooth blend between the two clips</li>
          <li><b>Fade through Black</b> — clip fades to black, next fades in</li>
          <li><b>Cross Dissolve</b> — both clips blend during the transition</li>
          <li><b>Wipe Left / Right</b> — new clip wipes across the screen</li>
          <li><b>Slide Left / Right</b> — new clip slides in from the side</li>
          <li><b>Zoom In</b> — zooms into the cut point</li>
          <li><b>Pixelize</b> — pixelates out then in (fun/retro)</li>
          <li><b>Circle Open</b> — circle opens to reveal next clip</li>
        </ul>

        <h3>How to set a transition</h3>
        <ol>
          <li>Select a clip</li>
          <li>Press <b>E</b> → <b>Transition</b> tab</li>
          <li>Choose a transition type and duration</li>
          <li>This transition plays at the END of the selected clip going into the next clip</li>
        </ol>

        <h3>Auto-suggest transitions (smart placement)</h3>
        <p>Go to <b>Effects → Auto-Suggest Transitions</b>. The app will:</p>
        <ul>
          <li>Analyse the audio at every clip boundary</li>
          <li>If the boundary is <b>silent</b> → add a Fade or Dissolve (safe)</li>
          <li>If <b>dialogue is detected</b> → keep a hard cut (preserves speech)</li>
        </ul>
        <p>This ensures transitions never interrupt someone mid-sentence.</p>

        <h3>Exporting with transitions</h3>
        <p>Transitions only work when you use <b>Effects → Export as Single Video</b>
        (or Effects → Export as Single, Ctrl+Shift+M). Individual clip exports ignore
        transitions.</p>
        ➡ <a href="#speed">Speed Changes</a> &nbsp;|&nbsp;
           <a href="#sfx">Sound Effects</a>
        """,
    },
    {
        "id": "sfx",
        "title": "Sound Effects",
        "content": """
        <h2>Sound Effects</h2>
        <p>Add short audio effects — whooshes, booms, dings — at specific points
        in a clip. These mix over the original audio during export.</p>

        <h3>Built-in effects</h3>
        <ul>
          <li><b>Whoosh</b> — quick air sound, great at the start of a speed ramp</li>
          <li><b>Boom</b> — low impact sound, good for dramatic moments or hard cuts</li>
          <li><b>Swoosh Up</b> — rising tone, works for menu transitions</li>
          <li><b>Ding</b> — bright success sound for wins</li>
          <li><b>Tension Riser</b> — subtle rising tone for dramatic moments</li>
        </ul>

        <h3>How to add sound effects</h3>
        <ol>
          <li>Select a clip, press <b>E</b></li>
          <li>Click the <b>Sound FX</b> tab</li>
          <li>Choose an effect, set the offset (when it plays, in seconds from clip start)</li>
          <li>Adjust the volume (0.0 to 1.0)</li>
          <li>Click "+ Add"</li>
          <li>You can add multiple effects per clip</li>
        </ol>

        <h3>Auto-suggest SFX (MrBeast style)</h3>
        <p>Go to <b>Effects → Auto-Suggest Sound Effects</b>. The app will:</p>
        <ul>
          <li>Add a <b>Whoosh</b> to the start of any clip with 2× speed or higher</li>
          <li>Add a subtle <b>Boom</b> to hard-cut endings for punch</li>
        </ul>

        <h3>Add your own sound effects</h3>
        <p>Drop any <code>.wav</code>, <code>.mp3</code>, or <code>.m4a</code> files into:</p>
        <p><code>resources/sfx/</code></p>
        <p>They will automatically appear in the effects dropdown.</p>
        ➡ <a href="#transitions">Transitions</a> &nbsp;|&nbsp;
           <a href="#audio">Audio Enhancement</a>
        """,
    },
    {
        "id": "audio",
        "title": "Audio Enhancement",
        "content": """
        <h2>Audio Enhancement</h2>
        <p>This is for the common gaming stream problem: <i>your voice comes through
        loud and clear, but teammates' mics get drowned out by game audio.</i></p>

        <h3>What it can do</h3>
        <ul>
          <li><b>Voice Boost</b> — raises the 300 Hz–3.4 kHz range (human speech
              frequencies) relative to game bass noise</li>
          <li><b>Game Bass Reduction</b> — cuts the low rumble (explosions, music bass)
              that floods over quiet voices</li>
          <li><b>Dynamic Compression</b> — brings up the quietest parts of speech
              so they're easier to hear</li>
          <li><b>Loudness Normalization</b> — adjusts your clip to YouTube's target
              volume (-16 LUFS) so it doesn't sound too quiet or too loud</li>
          <li><b>Noise Reduction</b> — reduces background hiss and constant noise</li>
        </ul>

        <h3>How to apply</h3>
        <ol>
          <li>Select a clip, press <b>E</b></li>
          <li>Click the <b>Audio</b> tab</li>
          <li>Pick a preset, or use the sliders for custom settings</li>
          <li>Click <b>Analyse this clip's audio</b> for automatic recommendations</li>
        </ol>

        <h3>Presets explained</h3>
        <table border="1" cellpadding="5" style="border-collapse:collapse; width:100%;">
          <tr style="background:#21262d;"><th>Preset</th><th>Best for</th></tr>
          <tr><td>None</td><td>Your audio is already balanced</td></tr>
          <tr><td>Voice Boost — Light</td><td>Voice slightly quiet but audible</td></tr>
          <tr><td>Voice Boost — Strong</td><td>Teammate mic very quiet, game floods it</td></tr>
          <tr><td>Duck Game Audio</td><td>Game music/effects covering voice</td></tr>
          <tr><td>Clean &amp; Loud</td><td>Full cleanup for YouTube upload</td></tr>
          <tr><td>Normalize Loudness</td><td>Just fix the volume level</td></tr>
        </table>

        <h3>Limitations</h3>
        <p>Perfect voice isolation from mixed audio requires AI tools
        (Demucs, Spleeter) which are large downloads not currently bundled.
        The filters above use equalizer and compression to improve intelligibility
        significantly, but cannot fully separate a quiet mic from loud game audio
        if they overlap in frequency.</p>
        <p>For best results, encourage teammates to use better microphone placement
        or check game/OBS settings for mic volume balance before recording.</p>
        ➡ <a href="#picture">Picture Adjustments</a>
        """,
    },
    {
        "id": "picture",
        "title": "Picture Adjustments",
        "content": """
        <h2>Picture Adjustments</h2>
        <p>If your footage is too dark, too flat, too washed out, or just needs a little
        punch before export, you can apply per-clip picture correction.</p>

        <h3>Available controls</h3>
        <ul>
          <li><b>Brightness</b> — lift dark footage or tone down over-bright clips</li>
          <li><b>Contrast</b> — make highlights and shadows pop more</li>
          <li><b>Saturation</b> — boost or reduce color intensity</li>
          <li><b>Gamma</b> — rebalance the midtones without crushing everything</li>
          <li><b>Sharpen</b> — slight detail boost for soft-looking captures</li>
        </ul>

        <h3>How to use it</h3>
        <ol>
          <li>Select a clip and press <b>E</b></li>
          <li>Open the <b>Picture</b> tab</li>
          <li>Adjust the sliders/spin boxes until the clip has the look you want</li>
          <li>Export — the picture adjustments are applied during render</li>
        </ol>

        <h3>When to use it</h3>
        <ul>
          <li>Dark interiors that need a brightness lift</li>
          <li>Flat footage that needs more contrast</li>
          <li>Dull color that needs more saturation</li>
          <li>Slightly soft recordings that need a little sharpen</li>
        </ul>

        ➡ <a href="#speed">Speed Changes</a> &nbsp;|&nbsp;
           <a href="#export">Exporting</a>
        """,
    },
    {
        "id": "projects",
        "title": "Projects and Autosave",
        "content": """
        <h2>Projects and Autosave</h2>
        <p>The editor saves your session as a <code>.gfve</code> project file so you can
        close the app and resume later with clips, effects, transitions, SFX, and captions intact.</p>

        <h3>Save and load</h3>
        <ul>
          <li><b>Ctrl+S</b> — save project</li>
          <li><b>Ctrl+Shift+S</b> — save project as</li>
          <li><b>Ctrl+Shift+O</b> — open project</li>
        </ul>

        <h3>Autosave and recovery</h3>
        <p>The app autosaves in the background. After a crash or forced restart,
        you will be prompted to recover the last session.</p>

        <h3>What is stored</h3>
        <ul>
          <li>Clip boundaries and names</li>
          <li>Speed, transitions, SFX, audio, picture settings</li>
          <li>Auto-captions and caption edits</li>
        </ul>
        """,
    },
    {
        "id": "settings",
        "title": "Settings and Shortcuts",
        "content": """
        <h2>Settings and Shortcuts</h2>
        <p>Use <b>File → Settings</b> (Ctrl+,) to tune editor behavior.</p>

        <h3>Main settings</h3>
        <ul>
          <li>Auto-save interval</li>
          <li>Proxy defaults and playback behavior</li>
          <li>Scene-detection sensitivity</li>
          <li>Keyboard shortcuts</li>
        </ul>

        <h3>FFmpeg tools page</h3>
        <ul>
          <li>Validate FFmpeg availability</li>
          <li>Check tool status and troubleshoot setup</li>
        </ul>
        """,
    },
    {
        "id": "captions",
        "title": "Captions and Viral Styles",
        "content": """
        <h2>Captions and Viral Styles</h2>
        <p>Auto-captions are generated from speech-region timing and then edited manually
        for wording, style, and timing polish.</p>

        <h3>Workflow</h3>
        <ol>
          <li>Run Detection → Auto-Cut Boring Parts with auto-captions enabled</li>
          <li>Open a clip in Effects (E) → <b>Captions</b></li>
          <li>Edit text, start/end time, font name, and effect style</li>
        </ol>

        <h3>Style ideas</h3>
        <ul>
          <li>Bold all-caps for reactions</li>
          <li>Short punch lines per beat for retention</li>
          <li>Use pop/flicker effects sparingly on key words</li>
        </ul>
        """,
    },
    {
        "id": "updates",
        "title": "App and FFmpeg Updates",
        "content": """
        <h2>App and FFmpeg Updates</h2>
        <p>You can now keep source installs up to date directly from inside the app.</p>

        <h3>Source code updates (Git)</h3>
        <ul>
          <li>Open <b>Settings → Tools &amp; FFmpeg</b></li>
          <li>Use <b>Check Update Status</b> to compare local branch vs remote</li>
          <li>Use <b>Pull Latest Updates Now</b> for an immediate fast-forward update</li>
          <li>Optional: enable <b>Pull latest updates on launch</b></li>
        </ul>
        <p><i>Safety:</i> Pull is blocked when local uncommitted changes exist.
        Commit or stash your changes first.</p>

        <h3>Clone latest source</h3>
        <ul>
          <li>Set a destination folder in Settings</li>
          <li>Click <b>Clone Latest Source</b></li>
          <li>A fresh copy is created in that folder</li>
        </ul>

        <h3>FFmpeg auto-bootstrap and update</h3>
        <ul>
          <li>Enable <b>Auto-install/update bundled FFmpeg on launch</b></li>
          <li>Set <b>FFmpeg zip URL</b> (default points to a Windows build zip)</li>
          <li>Click <b>Install / Update FFmpeg Now</b> to force refresh</li>
        </ul>
        <p>This is useful when the repo excludes large FFmpeg binaries,
        or when you want a newer FFmpeg build without rerunning full setup.</p>
        """,
    },
    {
        "id": "gpu",
        "title": "GPU Acceleration",
        "content": """
        <h2>GPU Acceleration</h2>
        <p>The app attempts hardware-assisted decode/encode across playback,
        proxies, analysis scans, and re-encode export paths when your system supports it.</p>

        <h3>What uses GPU preference</h3>
        <ul>
          <li>Preview decode (Qt FFmpeg backend)</li>
          <li>Proxy generation</li>
          <li>Accurate/effects export and single-video transition render</li>
          <li>Frame extraction and boring-part analysis scans</li>
        </ul>

        <h3>Encoders (preferred order)</h3>
        <p><code>h264_nvenc</code> → <code>h264_qsv</code> → <code>h264_amf</code> → fallback <code>libx264</code>.</p>

        <h3>Important limits</h3>
        <p>Actual GPU usage depends on codec support, driver state, FFmpeg build,
        and whether a path is stream-copy (which does not re-encode).</p>
        """,
    },
]


def get_help_tip_pool() -> list[str]:
  """Return a large rotating pool of concise tips built from all help topics."""
  tips: list[str] = []
  for topic in _TOPICS:
    title = (topic.get("title") or "").strip()
    content = topic.get("content") or ""

    # Strip HTML while preserving sentence boundaries.
    plain = re.sub(r"<br\s*/?>", ". ", content, flags=re.IGNORECASE)
    plain = re.sub(r"</(p|li|h2|h3|ol|ul)>", ". ", plain, flags=re.IGNORECASE)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = html.unescape(plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    if not plain:
      continue

    # Split into short, readable tips.
    parts = re.split(r"(?<=[.!?])\s+", plain)
    for part in parts:
      p = re.sub(r"\s+", " ", part).strip(" .\t\r\n")
      if not p:
        continue
      # Keep tips readable in status bar/progress dialog.
      word_count = len(p.split())
      if word_count < 4:
        continue
      if word_count > 36:
        p = " ".join(p.split()[:36]).rstrip(" ,;:") + "..."
      tips.append(f"[{title}] {p}")

  # De-duplicate while preserving order.
  unique: list[str] = []
  seen = set()
  for tip in tips:
    if tip not in seen:
      unique.append(tip)
      seen.add(tip)
  return unique


class HelpWindow(QMainWindow):
    """Singleton help window — call HelpWindow.get_instance() to get the instance."""

    _instance: Optional["HelpWindow"] = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Help — {APP_NAME}")
        self.resize(820, 620)

        # Toolbar
        tb = QToolBar("Navigation")
        tb.setMovable(False)
        self.addToolBar(tb)
        self._back_action = QAction("◀ Back", self)
        self._back_action.triggered.connect(self._go_back)
        tb.addAction(self._back_action)

        # Search
        self._search = QLineEdit()
        self._search.setPlaceholderText("  Search help like Google (title + full content)…")
        self._search.setFixedWidth(220)
        self._search.textChanged.connect(self._filter_topics)
        tb.addWidget(self._search)

        # Main area
        splitter = QSplitter(Qt.Horizontal)

        # Topic list
        self._topic_list = QListWidget()
        self._topic_list.setFixedWidth(180)
        self._topic_list.setStyleSheet("QListWidget { border: none; }")
        self._topic_by_id = {t["id"]: t for t in _TOPICS}
        self._topic_order = [t["id"] for t in _TOPICS]
        self._topic_search_text = {
          t["id"]: self._topic_to_search_text(t)
          for t in _TOPICS
        }
        self._set_topic_list(self._topic_order)
        self._topic_list.currentItemChanged.connect(self._on_topic_selected)
        splitter.addWidget(self._topic_list)

        # Content pane
        self._browser = QTextBrowser()
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_link_clicked)
        font = QFont("Segoe UI", 11)
        self._browser.setFont(font)
        splitter.addWidget(self._browser)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # Status bar
        self.statusBar().showMessage(
            f"{APP_NAME} v{APP_VERSION}  |  Press F1 anywhere in the app to open help"
        )

        self._history: list[str] = []
        self.show_topic("welcome")

    # ── Public API ────────────────────────────────────────────────────────────
    def show_topic(self, topic_id: str):
      if topic_id not in self._topic_order:
        self._load_topic(topic_id)
        return
      # Ensure topic is visible in filtered mode.
      if self._topic_list.findItems("*", Qt.MatchWildcard):
        present_ids = {
          self._topic_list.item(i).data(Qt.UserRole)
          for i in range(self._topic_list.count())
        }
        if topic_id not in present_ids:
          self._set_topic_list(self._topic_order)
        for i in range(self._topic_list.count()):
            item = self._topic_list.item(i)
            if item.data(Qt.UserRole) == topic_id:
                self._topic_list.setCurrentItem(item)
                return
        # fallback: just load content
        self._load_topic(topic_id)

    @classmethod
    def get_instance(cls, parent=None) -> "HelpWindow":
        if cls._instance is None:
            cls._instance = cls(parent)
        return cls._instance

    # ── Internal ──────────────────────────────────────────────────────────────
    def _on_topic_selected(self, current, previous):
        if current:
            tid = current.data(Qt.UserRole)
            if self._history and self._history[-1] == tid:
                pass
            else:
                self._history.append(tid)
            self._load_topic(tid)

    def _load_topic(self, topic_id: str):
      topic = self._topic_by_id.get(topic_id)
      if topic is not None:
        html_body = (
          f"<p style='color:#8b949e; margin:0 0 8px 0;'><small>Topic: {topic_id}</small></p>"
          f"{topic['content']}"
        )
        html_out = self._wrap_html(topic["title"], html_body)
        self._browser.setHtml(html_out)
        return
        self._browser.setPlainText(f"Topic '{topic_id}' not found.")

    def _wrap_html(self, title: str, body: str) -> str:
        return f"""
        <html><head><style>
          body  {{ font-family: 'Segoe UI', sans-serif; font-size: 13px;
                  color: #e6edf3; background: #0d1117; margin: 16px; }}
          h2    {{ color: #f0a030; border-bottom: 1px solid #30363d;
                  padding-bottom: 4px; }}
          h3    {{ color: #e6a817; margin-top: 16px; }}
          a     {{ color: #58a6ff; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
          code  {{ background: #21262d; padding: 1px 4px;
                  border-radius: 3px; font-size: 12px; }}
          table {{ border-color: #30363d; width: 100%; margin-top: 8px; }}
          th    {{ background: #21262d; color: #f0a030; }}
          td, th {{ padding: 5px 8px; }}
          ul, ol {{ padding-left: 20px; line-height: 1.7; }}
          li    {{ margin-bottom: 4px; }}
        </style></head>
        <body>{body}</body></html>
        """

    def _on_link_clicked(self, url: QUrl):
        frag = url.fragment()
        if frag:
            self.show_topic(frag)

    def _go_back(self):
        if len(self._history) > 1:
            self._history.pop()
            prev = self._history[-1]
            self._load_topic(prev)

    def _filter_topics(self, text: str):
      q = (text or "").strip().lower()
      if not q:
        self._set_topic_list(self._topic_order)
        self.statusBar().showMessage(
          f"{APP_NAME} v{APP_VERSION}  |  Showing all {len(self._topic_order)} help topics"
        )
        return

      terms = [t for t in re.split(r"\s+", q) if t]
      scored: list[tuple[int, str]] = []
      for topic_id in self._topic_order:
        topic = self._topic_by_id[topic_id]
        hay = self._topic_search_text[topic_id]
        title = topic["title"].lower()

        if not any(term in hay for term in terms):
          continue

        score = 0
        for term in terms:
          if term in title:
            score += 12
          if term in topic_id:
            score += 9
          count = hay.count(term)
          score += min(8, count)
        if q in title:
          score += 25
        if q in hay:
          score += 10
        scored.append((score, topic_id))

      scored.sort(key=lambda x: (-x[0], self._topic_order.index(x[1])))
      ordered = [topic_id for _, topic_id in scored]
      self._set_topic_list(ordered)
      self.statusBar().showMessage(
        f"Search: '{text}'  |  {len(ordered)} topic{'s' if len(ordered) != 1 else ''} matched"
      )

    def _set_topic_list(self, topic_ids: list[str]):
      current = None
      item = self._topic_list.currentItem()
      if item is not None:
        current = item.data(Qt.UserRole)

      self._topic_list.blockSignals(True)
      self._topic_list.clear()
      for topic_id in topic_ids:
        topic = self._topic_by_id[topic_id]
        it = QListWidgetItem(topic["title"])
        it.setData(Qt.UserRole, topic_id)
        self._topic_list.addItem(it)
      self._topic_list.blockSignals(False)

      if self._topic_list.count() == 0:
        self._browser.setHtml(self._wrap_html("No Results", "<p>No help topics match your search yet.</p>"))
        return

      target_id = current if current in topic_ids else topic_ids[0]
      for i in range(self._topic_list.count()):
        it = self._topic_list.item(i)
        if it.data(Qt.UserRole) == target_id:
          self._topic_list.setCurrentItem(it)
          break

    @staticmethod
    def _topic_to_search_text(topic: dict) -> str:
      plain = re.sub(r"<[^>]+>", " ", topic.get("content", ""))
      plain = html.unescape(plain)
      plain = re.sub(r"\s+", " ", plain).strip().lower()
      return f"{topic.get('id', '')} {topic.get('title', '')} {plain}".lower()

    def closeEvent(self, event):
        # Hide instead of close so the instance is preserved
        self.hide()
        event.ignore()
