# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-06-14

### Added
- Initial release.
- Tkinter desktop GUI for the `markitdown` CLI with a dark theme.
- Drag-and-drop file input via `tkinterdnd2`, with graceful fallback to a file
  picker when it is unavailable.
- "Choose files…" picker and batch conversion of multiple files.
- Output-folder prompt each run (defaults to `~/Documents`).
- Background-thread conversion with a thread-safe queue polled via `after()`,
  keeping the UI responsive.
- Scrolling log with per-file ✓/✗ results and a status line.
- `markitdown` executable discovery via `shutil.which` with a
  `~/.local/bin/markitdown` fallback, and a clear message when it is missing.
- `install.sh` / `uninstall.sh`, `.desktop` entry, and app icon (SVG + PNG).
- `pyproject.toml` with a `markitdown-gui` console entry point.
- Headless `xvfb` smoke test and GitHub Actions CI.
- AppImage / `.deb` packaging scripts under `packaging/`.

[Unreleased]: https://github.com/AEdgecombe/markitdown-gui/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/AEdgecombe/markitdown-gui/releases/tag/v0.1.0
