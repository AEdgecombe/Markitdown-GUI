"""Shared pytest fixtures."""


import pytest

import markitdown_gui.app as app


def has_markitdown() -> bool:
    return app.find_markitdown() is not None


requires_markitdown = pytest.mark.skipif(
    not has_markitdown(),
    reason="markitdown CLI not installed (pipx install 'markitdown[all]')",
)


def has_display() -> bool:
    import os

    return bool(os.environ.get("DISPLAY"))


requires_display = pytest.mark.skipif(
    not has_display(),
    reason="no X display available (run under xvfb-run)",
)


@pytest.fixture
def sample_html(tmp_path):
    p = tmp_path / "sample.html"
    p.write_text(
        "<html><head><title>Sample</title></head>"
        "<body><h1>Hello</h1><p>This is a <b>test</b> document.</p>"
        "<ul><li>one</li><li>two</li></ul></body></html>",
        encoding="utf-8",
    )
    return p
