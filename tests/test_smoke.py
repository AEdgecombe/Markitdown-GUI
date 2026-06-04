"""Headless GUI smoke test.

Constructs the real application window (under xvfb in CI), drives the
background conversion worker on a sample HTML file through the same
queue/`after()` machinery the UI uses, and asserts the `.md` is produced.
"""

import time

import markitdown_gui.app as app
from markitdown_gui.app import App, make_root

from .conftest import requires_display, requires_markitdown


@requires_display
def test_window_constructs():
    """The window builds and its widgets exist without raising."""
    root = make_root()
    try:
        gui = App(root)
        root.update()  # force a layout pass
        assert gui.convert_btn is not None
        assert gui.log is not None
        assert gui.status_var.get()  # has some status text
    finally:
        root.destroy()


@requires_display
@requires_markitdown
def test_end_to_end_conversion_via_worker(sample_html, tmp_path):
    """Run the worker the GUI uses and pump the queue until done."""
    root = make_root()
    try:
        gui = App(root)
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        # Drive the worker directly (mirrors what _start_conversion launches).
        gui._run_worker(app.find_markitdown(), [sample_html], str(out_dir))

        # Pump Tk's event loop so the queue drains and the log updates.
        done = False
        deadline = time.time() + 30
        while time.time() < deadline:
            gui._drain_queue()
            root.update()
            if "Done" in gui.status_var.get():
                done = True
                break
            time.sleep(0.05)

        assert done, f"worker never finished; status={gui.status_var.get()!r}"
        expected = out_dir / f"{sample_html.stem}.md"
        assert expected.is_file(), "expected .md output was not produced"
        assert "Hello" in expected.read_text()
    finally:
        root.destroy()
