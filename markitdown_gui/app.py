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
# Theme — a modern, flat dark palette (charcoal / blue / green).
# --------------------------------------------------------------------------- #
BG = "#16191d"          # app background (deep charcoal)
SURFACE = "#1e2329"     # cards / panels
SURFACE_2 = "#262d35"   # raised surfaces (drop zone, chips)
SURFACE_3 = "#2f3842"   # hover on raised surfaces
FG = "#e8ebee"          # primary text
FG_MUTED = "#8a96a3"    # secondary text
FG_FAINT = "#5b6671"    # tertiary text / icons
ACCENT = "#4a90d9"      # blue accent
ACCENT_HOVER = "#5b9fe6"
ACCENT_DOWN = "#3d7ec0"
SUCCESS = "#5cb85c"     # green success
SUCCESS_DIM = "#3f7a3f"
ERROR = "#e2555a"       # red failure
BORDER = "#2c343d"
BORDER_STRONG = "#3a444f"

# Backwards-compatible aliases (kept so existing imports keep working).
BG_ALT = SURFACE
BG_DROP = SURFACE_2

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
from tkinter import font as tkfont

# Optional drag-and-drop support.
try:  # pragma: no cover - exercised by integration, not unit tests
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _DND_AVAILABLE = True
except Exception:  # ImportError, or a broken X/Tcl install
    DND_FILES = None
    TkinterDnD = None
    _DND_AVAILABLE = False

# WM_CLASS / .desktop StartupWMClass used so the dock/taskbar matches the app
# to its .desktop entry and shows the right icon.
WM_CLASS = "markitdown-gui"


def make_root() -> tk.Tk:
    """Create the Tk root, using TkinterDnD's root when drag-and-drop is present.

    A class name is set so the window's WM_CLASS matches the installed
    ``markitdown-gui.desktop`` entry (and its ``StartupWMClass``), which is what
    GNOME/Ubuntu use to show the correct icon in the dock/taskbar.
    """
    if _DND_AVAILABLE:
        try:
            return TkinterDnD.Tk(className=WM_CLASS)
        except Exception:
            return TkinterDnD.Tk()
    return tk.Tk(className=WM_CLASS)


def _icon_candidates() -> list[Path]:
    """Possible locations of the app icon PNG, most-specific first."""
    here = Path(__file__).resolve().parent
    return [
        here / "icon.png",                                   # shipped in package
        here.parent / "assets" / "icon.png",                 # running from source
        Path.home() / ".local/share/icons/hicolor/256x256/apps/markitdown-gui.png",
        Path("/usr/share/icons/hicolor/256x256/apps/markitdown-gui.png"),
    ]


def load_icon(root: tk.Misc) -> tk.PhotoImage | None:
    """Load the app icon as a Tk PhotoImage, or ``None`` if unavailable."""
    for path in _icon_candidates():
        if path.is_file():
            try:
                return tk.PhotoImage(file=str(path), master=root)
            except Exception:
                continue
    return None


def _pick_family(root: tk.Misc, preferred: list[str], fallback: str = "TkDefaultFont") -> str:
    """Return the first installed font family from ``preferred``."""
    try:
        available = {f.lower() for f in tkfont.families(root)}
    except Exception:
        return fallback
    for name in preferred:
        if name.lower() in available:
            return name
    return fallback


def _round_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kwargs):
    """Draw a rounded rectangle on ``canvas`` using a smoothed polygon."""
    r = min(r, abs(x2 - x1) / 2, abs(y2 - y1) / 2)
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class RoundedButton(tk.Canvas):
    """A flat, modern rounded button drawn on a canvas.

    Variants: ``primary`` (accent fill), ``secondary`` (surface fill), and
    ``ghost`` (transparent until hovered).
    """

    _VARIANTS = {
        "primary": dict(fill=ACCENT, hover=ACCENT_HOVER, down=ACCENT_DOWN,
                        text="#ffffff", border=None),
        "secondary": dict(fill=SURFACE_2, hover=SURFACE_3, down=SURFACE_2,
                          text=FG, border=BORDER_STRONG),
        "ghost": dict(fill="", hover=SURFACE_2, down=SURFACE_2,
                      text=FG_MUTED, border=None),
    }

    def __init__(self, master, text, command=None, *, variant="primary",
                 font=None, parent_bg=BG, padx=18, pady=11, radius=11, min_width=0):
        self._spec = dict(self._VARIANTS[variant])
        self._variant = variant
        self._parent_bg = parent_bg
        self._command = command
        self._text = text
        self._font = font or ("TkDefaultFont", 10)
        self._radius = radius
        self._padx, self._pady = padx, pady
        self._enabled = True
        self._state = "normal"

        f = tkfont.Font(family=self._font[0], size=self._font[1],
                        weight=self._font[2] if len(self._font) > 2 else "normal")
        text_w = f.measure(text)
        text_h = f.metrics("linespace")
        w = max(min_width, text_w + padx * 2)
        h = text_h + pady * 2

        super().__init__(master, width=w, height=h, bg=parent_bg,
                         highlightthickness=0, bd=0, takefocus=0)
        # NB: do not use self._w/_h — those are Tkinter's internal widget-path
        # attributes. Store our geometry under different names.
        self._cw, self._ch = w, h
        self._shape = None
        self._label = None
        self._draw("normal")

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _draw(self, state):
        self.delete("all")
        spec = self._spec
        if not self._enabled:
            fill = SURFACE if self._variant != "ghost" else self._parent_bg
            text_color = FG_FAINT
            border = BORDER
        else:
            fill = {"normal": spec["fill"], "hover": spec["hover"],
                    "down": spec["down"]}[state]
            text_color = spec["text"]
            border = spec["border"]
        outline = border or ""
        bw = 1 if border else 0
        if fill == "" and not self._enabled:
            fill = self._parent_bg
        if fill == "":
            # ghost at rest: paint parent bg so the canvas blends in
            fill = self._parent_bg
            outline = ""
            bw = 0
        self._shape = _round_rect(self, 1, 1, self._cw - 1, self._ch - 1,
                                  self._radius, fill=fill, outline=outline, width=bw)
        self._label = self.create_text(self._cw / 2, self._ch / 2, text=self._text,
                                       fill=text_color, font=self._font)
        self.configure(cursor="hand2" if self._enabled else "")

    def _on_enter(self, _):
        if self._enabled:
            self._state = "hover"
            self._draw("hover")

    def _on_leave(self, _):
        if self._enabled:
            self._state = "normal"
            self._draw("normal")

    def _on_press(self, _):
        if self._enabled:
            self._draw("down")

    def _on_release(self, event):
        if not self._enabled:
            return
        self._draw("hover")
        # Only fire if released over the button.
        if 0 <= event.x <= self._cw and 0 <= event.y <= self._ch and self._command:
            self._command()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self._draw("normal")

    def set_text(self, text: str):
        self._text = text
        self.itemconfigure(self._label, text=text)


class DropZone(tk.Canvas):
    """A large, modern drop target with a download glyph and helper text.

    Clicking it opens the file picker. When drag-and-drop is available, files
    can also be dropped onto it; the border highlights during a drag.
    """

    def __init__(self, master, on_files, on_click, height=176):
        super().__init__(master, height=height, bg=BG, highlightthickness=0, bd=0)
        self._on_files = on_files
        self._on_click = on_click
        self._active = False
        self._hover = False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", lambda e: self._on_click())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

        if _DND_AVAILABLE:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DropEnter>>", self._drop_enter)
            self.dnd_bind("<<DropLeave>>", self._drop_leave)

    # -- drawing ---------------------------------------------------------- #
    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 1:
            return
        highlight = self._active
        border = ACCENT if highlight else BORDER_STRONG
        fill = SURFACE_2 if (highlight or self._hover) else SURFACE
        glyph = ACCENT if highlight else (FG_MUTED if self._hover else FG_FAINT)

        _round_rect(self, 2, 2, w - 2, h - 2, 16, fill=fill, outline=border, width=2)
        self._dashed_outline(8, 8, w - 8, h - 8, 13, ACCENT if highlight else BORDER_STRONG)

        cx = w / 2
        cy = h / 2 - 22
        self._download_glyph(cx, cy, glyph)

        if _DND_AVAILABLE:
            t1, t2 = "Drag & drop files here", "or click to browse"
        else:
            t1, t2 = "Click to choose files", "drag-and-drop unavailable"
        self.create_text(cx, h / 2 + 26, text=t1, fill=FG,
                         font=(FAMILY_UI, 13, "bold"))
        self.create_text(cx, h / 2 + 48, text=t2, fill=FG_MUTED,
                         font=(FAMILY_UI, 10))

    def _dashed_outline(self, x1, y1, x2, y2, r, color):
        # A subtle dashed rounded outline drawn as straight dashed segments.
        self.create_line(x1 + r, y1, x2 - r, y1, fill=color, dash=(4, 4))
        self.create_line(x1 + r, y2, x2 - r, y2, fill=color, dash=(4, 4))
        self.create_line(x1, y1 + r, x1, y2 - r, fill=color, dash=(4, 4))
        self.create_line(x2, y1 + r, x2, y2 - r, fill=color, dash=(4, 4))

    def _download_glyph(self, cx, cy, color):
        # Down arrow into a tray — echoes the app icon.
        self.create_line(cx, cy - 22, cx, cy + 8, fill=color, width=4,
                         capstyle="round")
        self.create_polygon(cx - 13, cy - 2, cx + 13, cy - 2, cx, cy + 16,
                            fill=color, outline=color)
        self.create_line(cx - 22, cy + 22, cx - 22, cy + 30, cx + 22, cy + 30,
                         cx + 22, cy + 22, fill=color, width=4,
                         capstyle="round", joinstyle="round")

    # -- events ----------------------------------------------------------- #
    def _enter(self, _):
        self._hover = True
        self._draw()

    def _leave(self, _):
        self._hover = False
        self._draw()

    def _drop_enter(self, _):  # pragma: no cover - needs DnD/X
        self._active = True
        self._draw()
        return "copy"

    def _drop_leave(self, _):  # pragma: no cover - needs DnD/X
        self._active = False
        self._draw()
        return "copy"

    def _on_drop(self, event):  # pragma: no cover - needs DnD/X
        self._active = False
        self._draw()
        paths = self.tk.splitlist(event.data)
        self._on_files(paths)


# Resolved once the root exists (see App._init_fonts).
FAMILY_UI = "TkDefaultFont"
FAMILY_MONO = "TkFixedFont"


# Messages the worker thread posts onto the UI queue.
MSG_STATUS = "status"
MSG_LOG = "log"
MSG_RESULT = "result"
MSG_PROGRESS = "progress"
MSG_DONE = "done"


class App:
    """The MarkItDown GUI application window."""

    POLL_MS = 80

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.executable = find_markitdown()
        self.selected_files: list[Path] = []
        self.queue: queue.Queue[tuple] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._init_fonts()

        self.root.title("MarkItDown")
        self.root.configure(bg=BG)
        self.root.minsize(620, 660)
        try:
            self.root.geometry("680x740")
        except tk.TclError:
            pass

        # Window/taskbar icon.
        self._icon = load_icon(self.root)
        if self._icon is not None:
            try:
                self.root.iconphoto(True, self._icon)
            except tk.TclError:
                pass

        self._build_styles()
        self._build_ui()
        self._refresh_engine_status()

        self.root.after(self.POLL_MS, self._drain_queue)

    # -- fonts ------------------------------------------------------------- #
    def _init_fonts(self) -> None:
        global FAMILY_UI, FAMILY_MONO
        FAMILY_UI = _pick_family(
            self.root,
            ["Inter", "Cantarell", "Ubuntu", "Noto Sans", "DejaVu Sans"],
            "TkDefaultFont",
        )
        FAMILY_MONO = _pick_family(
            self.root,
            ["JetBrains Mono", "Cascadia Code", "Ubuntu Mono", "DejaVu Sans Mono"],
            "TkFixedFont",
        )
        self.f_title = (FAMILY_UI, 21, "bold")
        self.f_subtitle = (FAMILY_UI, 11)
        self.f_section = (FAMILY_UI, 11, "bold")
        self.f_body = (FAMILY_UI, 10)
        self.f_btn = (FAMILY_UI, 10, "bold")
        self.f_mono = (FAMILY_MONO, 10)

    # -- styling ----------------------------------------------------------- #
    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Muted.TLabel", background=BG, foreground=FG_MUTED)
        style.configure("Title.TLabel", background=BG, foreground=FG, font=self.f_title)
        style.configure("Sub.TLabel", background=BG, foreground=FG_MUTED,
                        font=self.f_subtitle)
        style.configure("Section.TLabel", background=BG, foreground=FG_MUTED,
                        font=self.f_section)
        # Slim, flat progress bar.
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=SURFACE_2, background=ACCENT, bordercolor=SURFACE_2,
            lightcolor=ACCENT, darkcolor=ACCENT, thickness=6, borderwidth=0,
        )
        # Dark scrollbar.
        style.configure("Vertical.TScrollbar", background=SURFACE_2,
                        troughcolor=BG, bordercolor=BG, arrowcolor=FG_MUTED,
                        relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", SURFACE_3)])

    # -- layout ------------------------------------------------------------ #
    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="TFrame", padding=(22, 20, 22, 16))
        outer.pack(fill="both", expand=True)

        # --- Header (icon + title) --- #
        header = ttk.Frame(outer, style="TFrame")
        header.pack(fill="x")
        if self._icon is not None:
            small = self._scaled_icon(self._icon, 44)
            self._header_icon = small
            tk.Label(header, image=small, bg=BG).pack(side="left", padx=(0, 14))
        titles = ttk.Frame(header, style="TFrame")
        titles.pack(side="left", anchor="w")
        ttk.Label(titles, text="MarkItDown", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Convert documents to clean Markdown",
                  style="Sub.TLabel").pack(anchor="w", pady=(1, 0))

        # --- Drop zone --- #
        self.drop_zone = DropZone(outer, on_files=self._add_files,
                                  on_click=self._choose_files)
        self.drop_zone.pack(fill="x", pady=(20, 0))

        # --- Queue header --- #
        qhead = ttk.Frame(outer, style="TFrame")
        qhead.pack(fill="x", pady=(18, 6))
        self.queue_label = ttk.Label(qhead, text="No files selected",
                                     style="Section.TLabel")
        self.queue_label.pack(side="left")
        self.clear_btn = RoundedButton(qhead, "Clear all", command=self._clear_files,
                                       variant="ghost", font=self.f_btn,
                                       parent_bg=BG, padx=12, pady=6)
        self.clear_btn.pack(side="right")

        # --- File queue (scrollable) --- #
        self.queue_wrap = tk.Frame(outer, bg=SURFACE, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.queue_canvas = tk.Canvas(self.queue_wrap, bg=SURFACE,
                                      highlightthickness=0, height=132, bd=0)
        self.queue_scroll = ttk.Scrollbar(self.queue_wrap, orient="vertical",
                                          style="Vertical.TScrollbar",
                                          command=self.queue_canvas.yview)
        self.queue_inner = tk.Frame(self.queue_canvas, bg=SURFACE)
        self._queue_window = self.queue_canvas.create_window(
            (0, 0), window=self.queue_inner, anchor="nw")
        self.queue_canvas.configure(yscrollcommand=self.queue_scroll.set)
        self.queue_inner.bind(
            "<Configure>",
            lambda e: self.queue_canvas.configure(
                scrollregion=self.queue_canvas.bbox("all")))
        self.queue_canvas.bind(
            "<Configure>",
            lambda e: self.queue_canvas.itemconfigure(self._queue_window, width=e.width))
        self.queue_canvas.pack(side="left", fill="both", expand=True)
        self.queue_scroll.pack(side="right", fill="y")
        self._empty_label = tk.Label(
            self.queue_inner, text="Selected files will appear here.",
            bg=SURFACE, fg=FG_FAINT, font=self.f_body, anchor="w", padx=14, pady=14)
        self._empty_label.pack(fill="x")
        self.queue_wrap.pack(fill="x")

        # --- Convert button + progress --- #
        action = ttk.Frame(outer, style="TFrame")
        action.pack(fill="x", pady=(18, 4))
        self.convert_btn = RoundedButton(
            action, "Convert to Markdown", command=self._start_conversion,
            variant="primary", font=self.f_btn, parent_bg=BG, padx=22, pady=12)
        self.convert_btn.pack(side="right")
        self.choose_btn = RoundedButton(
            action, "Choose files…", command=self._choose_files,
            variant="secondary", font=self.f_btn, parent_bg=BG, padx=18, pady=12)
        self.choose_btn.pack(side="right", padx=(0, 10))

        self.progress = ttk.Progressbar(outer, style="Accent.Horizontal.TProgressbar",
                                        mode="determinate")
        # Packed/unpacked on demand in _set_busy, anchored above the log.

        # --- Activity log --- #
        self._activity_lbl = ttk.Label(outer, text="ACTIVITY", style="Section.TLabel")
        self._activity_lbl.pack(anchor="w", pady=(14, 6))
        log_wrap = tk.Frame(outer, bg=SURFACE, highlightthickness=1,
                            highlightbackground=BORDER)
        log_wrap.pack(fill="both", expand=True)
        self.log = tk.Text(
            log_wrap, bg=SURFACE, fg=FG, insertbackground=FG, relief="flat",
            wrap="word", height=8, padx=14, pady=12, state="disabled",
            font=self.f_mono, spacing1=1, spacing3=3, borderwidth=0,
            highlightthickness=0)
        log_scroll = ttk.Scrollbar(log_wrap, orient="vertical",
                                   style="Vertical.TScrollbar", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("ok", foreground=SUCCESS)
        self.log.tag_configure("err", foreground=ERROR)
        self.log.tag_configure("info", foreground=FG_MUTED)
        self.log.tag_configure("accent", foreground=ACCENT)

        # --- Status bar --- #
        self.status_var = tk.StringVar(value="Ready.")
        status = ttk.Label(outer, textvariable=self.status_var, style="Muted.TLabel",
                           anchor="w")
        status.pack(fill="x", pady=(10, 0))

    def _scaled_icon(self, image: tk.PhotoImage, target: int) -> tk.PhotoImage:
        """Subsample the icon down to roughly ``target`` px for header use."""
        try:
            factor = max(1, round(image.width() / target))
            return image.subsample(factor, factor)
        except Exception:
            return image

    # -- engine detection -------------------------------------------------- #
    def _refresh_engine_status(self) -> None:
        if self.executable:
            self._log(f"Using markitdown at {self.executable}", "info")
            self._set_status("Ready.")
        else:
            self.convert_btn.set_enabled(False)
            msg = ("markitdown not found. Install it with: "
                   "pipx install 'markitdown[all]'")
            self._log(msg, "err")
            self._set_status("markitdown not found — see activity log.")

    # -- file selection ---------------------------------------------------- #
    def _choose_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Choose files to convert")
        if paths:
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
        self._refresh_queue()

    def _remove_file(self, path: Path) -> None:
        if path in self.selected_files:
            self.selected_files.remove(path)
            self._refresh_queue()

    def _clear_files(self) -> None:
        if not self.selected_files:
            return
        self.selected_files.clear()
        self._refresh_queue()
        self._set_status("Selection cleared.")

    def _refresh_queue(self) -> None:
        for child in self.queue_inner.winfo_children():
            child.destroy()

        n = len(self.selected_files)
        if n == 0:
            self.queue_label.configure(text="No files selected")
            tk.Label(self.queue_inner, text="Selected files will appear here.",
                     bg=SURFACE, fg=FG_FAINT, font=self.f_body, anchor="w",
                     padx=14, pady=14).pack(fill="x")
            return

        self.queue_label.configure(text=f"{n} file{'s' if n != 1 else ''} selected")
        for path in self.selected_files:
            self._build_queue_row(path)

    def _build_queue_row(self, path: Path) -> None:
        row = tk.Frame(self.queue_inner, bg=SURFACE)
        row.pack(fill="x", padx=8, pady=2)

        dot = tk.Label(row, text="●", bg=SURFACE, fg=ACCENT, font=(FAMILY_UI, 8))
        dot.pack(side="left", padx=(6, 8))

        name = self._ellipsize(path.name, 52)
        lbl = tk.Label(row, text=name, bg=SURFACE, fg=FG, font=self.f_body,
                       anchor="w")
        lbl.pack(side="left", fill="x", expand=True)

        rm = tk.Label(row, text="✕", bg=SURFACE, fg=FG_FAINT,
                      font=(FAMILY_UI, 11), cursor="hand2", padx=8)
        rm.pack(side="right")
        rm.bind("<Button-1>", lambda e, p=path: self._remove_file(p))
        rm.bind("<Enter>", lambda e: rm.configure(fg=ERROR))
        rm.bind("<Leave>", lambda e: rm.configure(fg=FG_FAINT))

        def hi(_):
            for w in (row, dot, lbl):
                w.configure(bg=SURFACE_2)
            rm.configure(bg=SURFACE_2)
        def lo(_):
            for w in (row, dot, lbl):
                w.configure(bg=SURFACE)
            rm.configure(bg=SURFACE)
        for w in (row, lbl, dot):
            w.bind("<Enter>", hi)
            w.bind("<Leave>", lo)

    @staticmethod
    def _ellipsize(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        keep = limit - 1
        head = keep // 2
        tail = keep - head
        return f"{text[:head]}…{text[-tail:]}"

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
        output_dir = filedialog.askdirectory(title="Choose output folder",
                                             initialdir=default_dir)
        if not output_dir:
            self._set_status("Conversion cancelled — no output folder.")
            return

        files = list(self.selected_files)
        self._set_busy(True, total=len(files))
        self._set_status(f"Converting {len(files)} file(s)…")
        self._log(f"Output folder: {output_dir}", "accent")

        self._worker = threading.Thread(
            target=self._run_worker, args=(self.executable, files, output_dir),
            daemon=True)
        self._worker.start()

    def _run_worker(self, executable: str, files: list[Path], output_dir: str) -> None:
        """Runs on a background thread; communicates only via the queue."""
        ok_count = 0
        for i, f in enumerate(files, 1):
            self.queue.put((MSG_STATUS, f"Converting {f.name}… ({i}/{len(files)})"))
            result = convert_file(executable, f, output_dir)
            if result.ok:
                ok_count += 1
            self.queue.put((MSG_RESULT, result))
            self.queue.put((MSG_PROGRESS, i))
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
                elif kind == MSG_PROGRESS:
                    self.progress.configure(value=payload)
                elif kind == MSG_DONE:
                    ok, total = payload
                    self._set_busy(False)
                    self._set_status(f"Done — {ok}/{total} converted.")
        except queue.Empty:
            pass
        self.root.after(self.POLL_MS, self._drain_queue)

    def _log_result(self, result: ConversionResult) -> None:
        if result.ok:
            self._log(f"✓  {result.input_path.name}  →  {result.output_path.name}", "ok")
        else:
            self._log(f"✗  {result.input_path.name}  —  {result.message}", "err")

    # -- small helpers ----------------------------------------------------- #
    def _set_busy(self, busy: bool, total: int = 0) -> None:
        self.convert_btn.set_enabled(not busy)
        self.choose_btn.set_enabled(not busy)
        self.clear_btn.set_enabled(not busy)
        if busy:
            self.progress.configure(maximum=total, value=0)
            self.progress.pack(fill="x", pady=(12, 2), before=self._activity_lbl)
            self.convert_btn.set_text("Converting…")
        else:
            self.progress.pack_forget()
            self.convert_btn.set_text("Convert to Markdown")

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
