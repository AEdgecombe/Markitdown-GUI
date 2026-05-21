"""MarkItDown GUI.

A thin Tkinter front-end for Microsoft's `markitdown` document-to-Markdown
converter. It does not modify markitdown; it shells out to the CLI via
subprocess. The conversion core (:func:`find_markitdown`, :func:`convert_file`)
is deliberately free of any Tk dependency so it can be unit-tested headlessly.
"""

from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
BG = "#1e2327"          # charcoal background
BG_ALT = "#272d33"      # slightly lighter panel
BG_DROP = "#2c343b"     # drop zone
FG = "#e6e9ec"          # primary text
FG_MUTED = "#9aa4ad"    # secondary text
ACCENT = "#4a90d9"      # blue accent
SUCCESS = "#5cb85c"     # green success
ERROR = "#d9534f"       # red failure
BORDER = "#3a434c"

CONVERT_TIMEOUT = 600   # seconds, per file


# --------------------------------------------------------------------------- #
# Conversion core (Tk-free, unit-testable)
# --------------------------------------------------------------------------- #
def find_markitdown() -> str | None:
    """Locate the markitdown executable.

    Tries ``$PATH`` first, then the pipx/pip ``--user`` install location
    ``~/.local/bin/markitdown``. Returns the absolute path or ``None``.
    """
    found = shutil.which("markitdown")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "markitdown"
    if fallback.is_file() and os.access(fallback, os.X_OK):
        return str(fallback)
    return None


@dataclass
class ConversionResult:
    """Outcome of converting a single file."""

    input_path: Path
    output_path: Path
    ok: bool
    message: str = ""


def convert_file(
    executable: str,
    input_path: os.PathLike | str,
    output_dir: os.PathLike | str,
    timeout: int = CONVERT_TIMEOUT,
) -> ConversionResult:
    """Convert one file to Markdown via ``markitdown <input> -o <output.md>``.

    Returns a :class:`ConversionResult`. Never raises for ordinary failures
    (non-zero exit, timeout, missing input) — those are reported on the result.
    """
    input_path = Path(input_path)
    output_path = Path(output_dir) / f"{input_path.stem}.md"

    if not input_path.is_file():
        return ConversionResult(input_path, output_path, False, "input file not found")

    try:
        proc = subprocess.run(
            [executable, str(input_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ConversionResult(
            input_path, output_path, False, f"timed out after {timeout}s"
        )
    except OSError as exc:
        return ConversionResult(input_path, output_path, False, str(exc))

    if proc.returncode != 0:
        detail = _last_meaningful_line(proc.stderr) or _last_meaningful_line(
            proc.stdout
        )
        return ConversionResult(
            input_path,
            output_path,
            False,
            detail or f"markitdown exited with code {proc.returncode}",
        )

    if not output_path.is_file():
        return ConversionResult(
            input_path, output_path, False, "markitdown reported success but wrote no file"
        )

    return ConversionResult(input_path, output_path, True, "")


def _last_meaningful_line(text: str) -> str:
    """Return the last non-blank line of ``text`` (markitdown's error summary)."""
    if not text:
        return ""
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line:
            return line
    return ""


def convert_batch(
    executable: str,
    inputs: Iterable[os.PathLike | str],
    output_dir: os.PathLike | str,
    on_result: Callable[[ConversionResult], None] | None = None,
    timeout: int = CONVERT_TIMEOUT,
) -> list[ConversionResult]:
    """Convert many files, invoking ``on_result`` after each one."""
    results: list[ConversionResult] = []
    for item in inputs:
        result = convert_file(executable, item, output_dir, timeout=timeout)
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
import tkinter as tk
from tkinter import filedialog, ttk

# Optional drag-and-drop support.
try:  # pragma: no cover - exercised by integration, not unit tests
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _DND_AVAILABLE = True
except Exception:  # ImportError, or a broken X/Tcl install
    DND_FILES = None
    TkinterDnD = None
    _DND_AVAILABLE = False


def make_root() -> tk.Tk:
    """Create the Tk root, using TkinterDnD's root when drag-and-drop is present."""
    if _DND_AVAILABLE:
        return TkinterDnD.Tk()
    return tk.Tk()


# Messages the worker thread posts onto the UI queue.
MSG_STATUS = "status"
MSG_LOG = "log"
MSG_RESULT = "result"
MSG_DONE = "done"


class App:
    """The MarkItDown GUI application window."""

    POLL_MS = 100

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.executable = find_markitdown()
        self.selected_files: list[Path] = []
        self.queue: queue.Queue[tuple] = queue.Queue()
        self._worker: threading.Thread | None = None

        self.root.title("MarkItDown")
        self.root.configure(bg=BG)
        self.root.minsize(560, 520)

        self._build_styles()
        self._build_ui()
        self._refresh_engine_status()

        self.root.after(self.POLL_MS, self._drain_queue)

    # -- styling ----------------------------------------------------------- #
    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=BG_ALT)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED)
        style.configure("Title.TLabel", background=BG, foreground=FG,
                        font=("Sans", 16, "bold"))
        style.configure(
            "Accent.TButton",
            background=ACCENT,
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(14, 8),
            font=("Sans", 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#3a7bc0"), ("disabled", BORDER)],
            foreground=[("disabled", FG_MUTED)],
        )
        style.configure(
            "Secondary.TButton",
            background=BG_ALT,
            foreground=FG,
            borderwidth=1,
            padding=(12, 8),
        )
        style.map("Secondary.TButton", background=[("active", BG_DROP)])

    # -- layout ------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = self.root
        outer = ttk.Frame(root, style="TFrame", padding=16)
        outer.pack(fill="both", expand=True)

        header = ttk.Label(outer, text="MarkItDown", style="Title.TLabel")
        header.pack(anchor="w")
        ttk.Label(
            outer,
            text="Convert documents to Markdown — drag files in or choose them.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 12))

        # Drop zone.
        self.drop_zone = tk.Frame(
            outer,
            bg=BG_DROP,
            highlightbackground=BORDER,
            highlightthickness=2,
            height=120,
        )
        self.drop_zone.pack(fill="x")
        self.drop_zone.pack_propagate(False)

        if _DND_AVAILABLE:
            drop_text = "Drag & drop files here"
        else:
            drop_text = "Drag & drop unavailable — use “Choose files…”"
        self.drop_label = tk.Label(
            self.drop_zone,
            text=drop_text,
            bg=BG_DROP,
            fg=FG_MUTED if not _DND_AVAILABLE else FG,
            font=("Sans", 11),
        )
        self.drop_label.place(relx=0.5, rely=0.5, anchor="center")

        if _DND_AVAILABLE:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)

        # Buttons.
        btn_row = ttk.Frame(outer, style="TFrame")
        btn_row.pack(fill="x", pady=12)
        self.choose_btn = ttk.Button(
            btn_row, text="Choose files…", style="Secondary.TButton",
            command=self._choose_files,
        )
        self.choose_btn.pack(side="left")
        self.clear_btn = ttk.Button(
            btn_row, text="Clear", style="Secondary.TButton",
            command=self._clear_files,
        )
        self.clear_btn.pack(side="left", padx=(8, 0))
        self.convert_btn = ttk.Button(
            btn_row, text="Convert", style="Accent.TButton",
            command=self._start_conversion,
        )
        self.convert_btn.pack(side="right")

        self.selection_label = ttk.Label(
            outer, text="No files selected.", style="Muted.TLabel"
        )
        self.selection_label.pack(anchor="w")

        # Log panel.
        ttk.Label(outer, text="Log", style="TLabel").pack(anchor="w", pady=(12, 4))
        log_wrap = tk.Frame(outer, bg=BORDER, highlightthickness=0)
        log_wrap.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_wrap,
            bg=BG_ALT,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            wrap="word",
            height=10,
            padx=10,
            pady=8,
            state="disabled",
        )
        scroll = ttk.Scrollbar(log_wrap, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("ok", foreground=SUCCESS)
        self.log.tag_configure("err", foreground=ERROR)
        self.log.tag_configure("info", foreground=FG_MUTED)
        self.log.tag_configure("accent", foreground=ACCENT)

        # Status line.
        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Label(
            outer, textvariable=self.status_var, style="Muted.TLabel", anchor="w"
        )
        status.pack(fill="x", pady=(8, 0))

    # -- engine detection -------------------------------------------------- #
    def _refresh_engine_status(self) -> None:
        if self.executable:
            self._log(f"Using markitdown at {self.executable}", "info")
            self._set_status("Ready.")
        else:
            self.convert_btn.state(["disabled"])
            msg = (
                "markitdown not found. Install it with: "
                "pipx install 'markitdown[all]'"
            )
            self._log(msg, "err")
            self._set_status("markitdown not found — see log.")

    # -- file selection ---------------------------------------------------- #
    def _choose_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Choose files to convert")
        if paths:
            self._add_files(paths)

    def _on_drop(self, event) -> None:  # pragma: no cover - requires DnD/X
        # tkinterdnd2 returns a Tcl list; splitlist handles brace-quoted paths.
        paths = self.root.tk.splitlist(event.data)
        self._add_files(paths)

    def _add_files(self, paths: Iterable[str]) -> None:
        added = 0
        existing = set(self.selected_files)
        for raw in paths:
            p = Path(raw).expanduser()
            if p.is_file() and p not in existing:
                self.selected_files.append(p)
                existing.add(p)
                added += 1
        if added:
            self._log(f"Added {added} file(s).", "info")
        self._update_selection_label()

    def _clear_files(self) -> None:
        self.selected_files.clear()
        self._update_selection_label()
        self._set_status("Selection cleared.")

    def _update_selection_label(self) -> None:
        n = len(self.selected_files)
        if n == 0:
            self.selection_label.configure(text="No files selected.")
        elif n == 1:
            self.selection_label.configure(text=f"1 file: {self.selected_files[0].name}")
        else:
            self.selection_label.configure(text=f"{n} files selected.")

    # -- conversion -------------------------------------------------------- #
    def _start_conversion(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        if not self.executable:
            self._refresh_engine_status()
            return
        if not self.selected_files:
            self._set_status("Select at least one file first.")
            return

        default_dir = str(Path.home() / "Documents")
        if not Path(default_dir).is_dir():
            default_dir = str(Path.home())
        output_dir = filedialog.askdirectory(
            title="Choose output folder", initialdir=default_dir
        )
        if not output_dir:
            self._set_status("Conversion cancelled — no output folder.")
            return

        files = list(self.selected_files)
        self._set_busy(True)
        self._set_status(f"Converting {len(files)} file(s)…")
        self._log(f"Output folder: {output_dir}", "accent")

        self._worker = threading.Thread(
            target=self._run_worker,
            args=(self.executable, files, output_dir),
            daemon=True,
        )
        self._worker.start()

    def _run_worker(self, executable: str, files: list[Path], output_dir: str) -> None:
        """Runs on a background thread; communicates only via the queue."""
        ok_count = 0
        for f in files:
            self.queue.put((MSG_STATUS, f"Converting {f.name}…"))
            result = convert_file(executable, f, output_dir)
            if result.ok:
                ok_count += 1
            self.queue.put((MSG_RESULT, result))
        self.queue.put((MSG_DONE, (ok_count, len(files))))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == MSG_STATUS:
                    self._set_status(payload)
                elif kind == MSG_LOG:
                    text, tag = payload
                    self._log(text, tag)
                elif kind == MSG_RESULT:
                    self._log_result(payload)
                elif kind == MSG_DONE:
                    ok, total = payload
                    self._set_busy(False)
                    self._set_status(f"Done — {ok}/{total} converted.")
        except queue.Empty:
            pass
        self.root.after(self.POLL_MS, self._drain_queue)

    def _log_result(self, result: ConversionResult) -> None:
        if result.ok:
            self._log(f"✓ {result.input_path.name} → {result.output_path.name}", "ok")
        else:
            self._log(f"✗ {result.input_path.name}: {result.message}", "err")

    # -- small helpers ----------------------------------------------------- #
    def _set_busy(self, busy: bool) -> None:
        state = ["disabled"] if busy else ["!disabled"]
        self.convert_btn.state(state)
        self.choose_btn.state(state)
        self.clear_btn.state(state)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _log(self, text: str, tag: str = "info") -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")


def main() -> None:
    root = make_root()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
