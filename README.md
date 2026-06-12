# MarkItDown GUI

A simple, native-feeling **Ubuntu/GNOME desktop app** for converting documents to
Markdown. It is a thin graphical front-end for Microsoft's excellent
[`markitdown`](https://github.com/microsoft/markitdown) command-line tool — drag in
your files, pick an output folder, and get clean `.md` files.

> **Relationship to upstream:** this is a *standalone* project. It does **not**
> fork or modify `markitdown`; it installs it as a dependency and calls the
> `markitdown` CLI via subprocess. All conversion credit belongs to the
> markitdown authors at Microsoft. See [NOTICE](NOTICE).

![screenshot placeholder](docs/screenshot.png)

<sub><i>Screenshot placeholder — drop a real screenshot at `docs/screenshot.png`.</i></sub>

## Features

- **Drag & drop** files in (via `tkinterdnd2`) **or** a "Choose files…" picker — both work.
- Graceful fallback: if drag-and-drop isn't available, the picker still works and
  the drop zone shows an "unavailable" message instead of crashing.
- **Pick the output folder each run** (defaults to `~/Documents`).
- **Batch conversion** of many files at once.
- **Scrolling log** with per-file ✓/✗ results and a live status line.
- Conversion runs on a **background thread**; the window never freezes.
- Dark theme (charcoal / blue / green).

## Supported formats

Via `markitdown[all]`: **PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx/.xls),
images** (OCR + EXIF metadata), **audio** (transcription), **HTML, CSV, JSON, XML,
EPub, ZIP archives**, and **YouTube URLs**. Some formats need extra system tools
(e.g. `ffmpeg` for audio). See the
[markitdown README](https://github.com/microsoft/markitdown) for details.

## Requirements

- Linux (built and tested on Ubuntu/GNOME)
- Python **3.10+** (markitdown requires it)
- Tkinter (`python3-tk`)

## Install

### Option A — `install.sh` (recommended for desktop use)

```bash
git clone https://github.com/AEdgecombe/markitdown-gui.git
cd markitdown-gui
./install.sh
```

This installs everything under `~/.local` (no system-wide writes except the apt
dependencies). It will:

1. Install the `markitdown` CLI via `pipx install 'markitdown[all]'` (if missing).
2. Ensure `python3-tk` is present (apt).
3. Install `tkinterdnd2` for drag-and-drop (`pip --user`; non-fatal if it fails).
4. Copy the app, a launcher, the icon, and a `.desktop` entry into `~/.local`.
5. Refresh the desktop + icon caches.

Then launch **MarkItDown** from your applications menu, or run `markitdown-gui`.

### Option B — `pip install`

```bash
pip install .            # core app + markitdown[all]
pip install '.[dnd]'     # also enable drag-and-drop
markitdown-gui
```

## Uninstall

```bash
./uninstall.sh
```

This removes the GUI but **leaves the `markitdown` CLI intact**. To remove the CLI
too: `pipx uninstall markitdown`.

## Usage

1. Launch **MarkItDown**.
2. Drag files onto the drop zone, or click **Choose files…**.
3. Click **Convert** and pick an output folder (defaults to `~/Documents`).
4. Watch the log for per-file results. Each input `report.pdf` becomes `report.md`.

The exact conversion call is `markitdown <input> -o <output>.md`.

## How it relates to upstream markitdown

`markitdown` does all the heavy lifting of parsing documents and producing
Markdown. This project only provides a friendly GUI around its CLI: file
selection, batch handling, threading, an output-folder prompt, and a log. It is
**not affiliated with or endorsed by Microsoft**. Both projects are MIT-licensed.

## Development

```bash
pip install '.[dev]'
ruff check .
pytest
```

The conversion core (`find_markitdown`, `convert_file` in
[`markitdown_gui/app.py`](markitdown_gui/app.py)) is deliberately Tk-free so it
can be unit-tested headlessly. The GUI smoke test runs under `xvfb` in CI.

## Packaging (stretch goal)

Scripts to build a double-click-installable **AppImage** or **`.deb`** live under
[`packaging/`](packaging/). See [`packaging/README.md`](packaging/README.md).
These are optional and not required to run the app.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

## License

[MIT](LICENSE) © Alexander Edgecombe. Underlying engine
[markitdown](https://github.com/microsoft/markitdown) is MIT © Microsoft — see
[NOTICE](NOTICE).
