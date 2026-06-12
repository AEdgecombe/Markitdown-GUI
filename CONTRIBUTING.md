# Contributing to MarkItDown GUI

Thanks for your interest! This is a small, focused project: a thin GUI over the
[`markitdown`](https://github.com/microsoft/markitdown) CLI. Bug reports, fixes,
and modest features are all welcome.

## Scope

This project deliberately stays a **front-end**. It shells out to the `markitdown`
CLI and does not parse documents itself. Conversion bugs and new-format requests
belong **upstream** at microsoft/markitdown. Things that belong **here**: the UI,
batch handling, error reporting, packaging, and desktop integration.

## Getting set up

```bash
git clone https://github.com/AEdgecombe/markitdown-gui.git
cd markitdown-gui
python3 -m venv .venv && source .venv/bin/activate
pip install '.[dev]'
```

You also need the engine on your PATH: `pipx install 'markitdown[all]'`.

## Running

```bash
python3 -m markitdown_gui     # or: markitdown-gui
```

## Tests & linting

```bash
ruff check .
pytest
```

GUI tests need a display. Locally that's your desktop session; in CI we run them
under `xvfb`:

```bash
xvfb-run -a pytest
```

Please keep the conversion core (`find_markitdown`, `convert_file`) free of any
Tkinter imports so it stays unit-testable without a display.

## Pull requests

1. Branch off `main`.
2. Keep changes focused; one logical change per PR.
3. Run `ruff check .` and `pytest` before pushing.
4. Update `CHANGELOG.md` under "Unreleased".
5. Match the existing code style (PEP 8, type hints, docstrings).

## Reporting bugs

Open an issue with your OS/Python version, how you installed (script vs pip),
whether `tkinterdnd2` is present, and the relevant lines from the in-app log.

By contributing you agree your contributions are licensed under the project's
[MIT License](LICENSE).
