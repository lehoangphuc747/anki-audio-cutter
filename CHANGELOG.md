# Changelog

All notable changes to the **Audio Card Cutter (AnkiVN)** add-on will be documented in this file.

---

## [1.2.0] - 2026-05-24

### Added
- **Enhanced Deck Selector**: Add, Rename, Delete decks directly from the selection dialog. Supports creating subdecks with parent deck selection (`Parent::Child` hierarchy).
- **Enhanced Note Type Selector**: Add (clone from existing), Rename, Delete note types directly from the selection dialog. Safety checks warn before deleting note types with existing notes.
- **Settings Dialog** (`⚙` button): New tabbed settings interface:
  - **General tab**: Configure output audio format (mp3/ogg/wav/m4a/aac), bitrate, and default audio field name.
  - **Shortcuts tab**: Reference table showing all keyboard shortcuts (primary keys + Alt alternatives).
  - **FFmpeg tab**: View installation status, version, binary location. Download FFmpeg if missing, or check for updates and auto-update.
- **FFmpeg Version Management**: `get_ffmpeg_version()`, `check_ffmpeg_latest_version()`, and `update_ffmpeg_windows()` — automated version checking and one-click update from gyan.dev.
- **Queue ▶ Play Button**: Play the selected queue item directly — plays cut audio if already processed, or previews the region from source audio if not yet cut.
- **Queue Single-Click → Waveform Highlight**: Clicking a queue item highlights its time region on the waveform and updates the Start/End input fields.
- ~50 new i18n strings for all new features.

### Fixed
- **BUG: Double-click to insert cut audio from queue** was not working because `_on_queue_item_double_clicked` handler was defined but never connected. Now properly wired via `qconnect`.

### Changed
- Queue item display now uses `○` (uncut) and `✓` (cut) prefixes for clearer visual status.
- Deck/notetype lists are refreshed from Anki database each time the selection dialog opens, ensuring CRUD changes are immediately reflected.

---

## [1.1.1] - 2026-05-24

### Added
- **Double-Click Waveform Reset**: Double-clicking the waveform widget clears the region and selects the full audio length.
- **Smart Active Field Insertion**: "Cut to Field" now automatically targets the currently focused text field editor in the dialog, falling back to the designated audio field if none is focused.
- **File-Only Undo**: Allowed undoing the "Cut to Field" operation by deleting the last cut media file even if no note has been created yet.

### Changed
- **Audacity-Like Playback Sync**: Pressing Play (or Space) while a region is selected now plays only the selected region and pauses at the end of the region. Pressing Play again restarts from the beginning of the selection.
- **Reorganized Actions Layout**: Moved "Cut to Field" (formerly Cut) and "Play Cut" buttons into the "Cut Region" group box, separating region-related audio actions from card/database actions.

---

## [1.1.0] - 2026-05-24

### Added
- **Interactive Waveform Slider (`AudioWaveformWidget`)**: Custom PyQt widget to render absolute audio amplitude profile in real-time.
- **Audacity-like Region Selection**: Supports mouse click to seek and mouse click-and-drag to select audio clip regions with visual highlight.
- **Playback Control Features**:
  - Speed modifier control (0.5x to 2.0x).
  - Reaction time offset to auto-shift start/end timings.
  - Auto hear on nudge (preview plays automatically when shift buttons are clicked).
- **Comprehensive ARCHITECTURE.md**: Detailed system-level documentation.

### Changed
- **Modular Refactoring**: Split monolithic `__init__.py` file (SRP violations) into structured files:
  - `ui.py`: Main UI setup and custom widgets.
  - `player.py`: Multi-version dynamic multimedia layer (PyQt5/PyQt6).
  - `ffmpeg_utils.py`: Audio extraction, cutting, and waveform data calculations.
  - `anki_interop.py`: Add-on config storage, note creation, and database interop.
  - `constants.py`: Centralized magic numbers, styling, and speeds.
- **Improved Undo Stability**: Switched from manually deleting notes (which corrupted Anki's main undo stack) to saving database checkpoints using Anki's native `col.undo()`.

### Fixed
- Import error crash on load due to Python 3.13 and PyQt6 API incompatibilities.
- Resolved `NameError: name 're' is not defined` inside `ui.py` parsing regex.

---

## [1.0.0] - 2026-05-22

### Added
- Initial release.
- Core dialog and manual cut fields (`Start`, `End`).
- Automatic background installation of FFmpeg for Windows.
- Standard note creator mapping audio files directly into card fields.
