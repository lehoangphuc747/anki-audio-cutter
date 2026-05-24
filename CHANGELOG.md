# Changelog

All notable changes to the **Audio Card Cutter (AnkiVN)** add-on will be documented in this file.

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
