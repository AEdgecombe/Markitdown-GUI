# Packaging (stretch goal)

These scripts build double-click-installable bundles. They are **optional** — the
core app runs fine via [`install.sh`](../install.sh) or `pip install .`. The
GUI does not require either bundle.

Both bundles still rely on the `markitdown` CLI being available at runtime
(installed via pipx/pip). Bundling the full `markitdown[all]` dependency tree
(which pulls in heavy native libraries) is out of scope here.

## AppImage

```bash
packaging/build_appimage.sh
```

Produces `MarkItDown-<version>-x86_64.AppImage` in the repo root. Requires an
internet connection on first run (downloads `appimagetool`). The AppImage bundles
the GUI and launches the system `python3`; it expects `python3-tk` and the
`markitdown` CLI to be present on the host.

## .deb

```bash
packaging/build_deb.sh
```

Produces `markitdown-gui_<version>_all.deb`. Install with:

```bash
sudo apt install ./markitdown-gui_<version>_all.deb
```

It declares `python3` and `python3-tk` as dependencies and recommends
`pipx`. After install, run `markitdown-gui` or launch **MarkItDown** from the
menu. You still need the engine: `pipx install 'markitdown[all]'`.

## Notes

- Version is read from `markitdown_gui/__init__.py`.
- Neither bundle writes outside its own prefix.
- These are intentionally simple; for a production release you may prefer
  `flatpak` or a PPA.
