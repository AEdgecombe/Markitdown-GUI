"""Unit tests for the Tk-free conversion core."""

from pathlib import Path

import markitdown_gui.app as app
from markitdown_gui.app import ConversionResult, convert_file, find_markitdown

from .conftest import requires_markitdown


def test_find_markitdown_uses_path(monkeypatch):
    monkeypatch.setattr(app.shutil, "which", lambda name: "/usr/bin/markitdown")
    assert find_markitdown() == "/usr/bin/markitdown"


def test_find_markitdown_local_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(app.shutil, "which", lambda name: None)
    fake_home = tmp_path
    bindir = fake_home / ".local" / "bin"
    bindir.mkdir(parents=True)
    exe = bindir / "markitdown"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setattr(app.Path, "home", classmethod(lambda cls: fake_home))
    assert find_markitdown() == str(exe)


def test_find_markitdown_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(app.shutil, "which", lambda name: None)
    monkeypatch.setattr(app.Path, "home", classmethod(lambda cls: tmp_path))
    assert find_markitdown() is None


def test_convert_file_missing_input(tmp_path):
    result = convert_file("markitdown", tmp_path / "nope.html", tmp_path)
    assert isinstance(result, ConversionResult)
    assert not result.ok
    assert "not found" in result.message


def test_convert_file_handles_bad_executable(tmp_path):
    src = tmp_path / "in.html"
    src.write_text("<h1>hi</h1>")
    result = convert_file("/nonexistent/markitdown-xyz", src, tmp_path)
    assert not result.ok
    assert result.message  # an OSError message was captured


def test_convert_file_reports_nonzero(tmp_path, monkeypatch):
    src = tmp_path / "in.html"
    src.write_text("<h1>hi</h1>")

    class FakeProc:
        returncode = 1
        stdout = ""
        stderr = "Traceback\nValueError: boom\n"

    monkeypatch.setattr(app.subprocess, "run", lambda *a, **k: FakeProc())
    result = convert_file("markitdown", src, tmp_path)
    assert not result.ok
    assert result.message == "ValueError: boom"


def test_output_path_naming(tmp_path, monkeypatch):
    src = tmp_path / "My Report.docx"
    src.write_text("x")
    out_md = tmp_path / "My Report.md"

    class FakeProc:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **k):
        # markitdown would write the file; emulate that here.
        Path(cmd[cmd.index("-o") + 1]).write_text("# converted")
        return FakeProc()

    monkeypatch.setattr(app.subprocess, "run", fake_run)
    result = convert_file("markitdown", src, tmp_path)
    assert result.ok
    assert result.output_path == out_md
    assert out_md.read_text() == "# converted"


@requires_markitdown
def test_real_conversion(sample_html, tmp_path):
    """End-to-end conversion using the actual markitdown CLI."""
    exe = find_markitdown()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    result = convert_file(exe, sample_html, out_dir)
    assert result.ok, result.message
    assert result.output_path.is_file()
    text = result.output_path.read_text()
    assert "Hello" in text
