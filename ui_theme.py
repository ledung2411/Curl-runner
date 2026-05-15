# ui_theme.py - optional ttkbootstrap theme integration with Tk fallback
# type: ignore
from __future__ import annotations

from tkinter import ttk

from constants import (
    BG, BG2, BG3, BORDER, ACCENT, TEXT, TEXT_DIM, ACTIVE_TEXT,
    SURFACE_ACTIVE, SURFACE_HOVER, FONT_FAMILY,
)

BOOTSTRAP_THEME = "flatly"

try:
    import ttkbootstrap as tb
    BOOTSTRAP_AVAILABLE = True
except Exception:
    tb = None
    BOOTSTRAP_AVAILABLE = False


def apply_modern_theme(root=None) -> str:
    """Apply the modern ttk theme layer and return the active theme name."""
    if BOOTSTRAP_AVAILABLE and tb is not None:
        try:
            style = tb.Style(theme=BOOTSTRAP_THEME)
            _configure_app_styles(style)
            return f"ttkbootstrap:{BOOTSTRAP_THEME}"
        except Exception:
            pass

    style = ttk.Style(root)
    try:
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    _configure_app_styles(style)
    return f"tk:{style.theme_use()}"


def _configure_app_styles(style) -> None:
    """Keep native ttk widgets aligned with the app's Postman-like palette."""
    base_font = (FONT_FAMILY, 9)
    small_bold = (FONT_FAMILY, 9, "bold")

    style.configure(
        "TCombobox",
        fieldbackground=BG2,
        background=BG3,
        foreground=TEXT,
        selectbackground=SURFACE_ACTIVE,
        selectforeground=ACTIVE_TEXT,
        arrowcolor=ACCENT,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        padding=6,
        font=base_font,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", BG2), ("focus", BG2)],
        background=[("active", SURFACE_HOVER), ("readonly", BG3)],
        foreground=[("readonly", TEXT)],
        bordercolor=[("focus", ACCENT)],
    )

    style.configure(
        "Treeview",
        background=BG2,
        foreground=TEXT,
        fieldbackground=BG2,
        borderwidth=0,
        rowheight=30,
        font=base_font,
    )
    style.configure(
        "Treeview.Heading",
        background=BG3,
        foreground=TEXT_DIM,
        borderwidth=0,
        padding=(8, 7),
        font=small_bold,
    )
    style.map(
        "Treeview",
        background=[("selected", SURFACE_ACTIVE)],
        foreground=[("selected", ACTIVE_TEXT)],
    )

    style.configure(
        "TNotebook",
        background=BG,
        borderwidth=0,
        tabmargins=(0, 4, 0, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=BG3,
        foreground=TEXT_DIM,
        borderwidth=0,
        padding=(14, 7),
        font=base_font,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", SURFACE_ACTIVE), ("active", SURFACE_HOVER)],
        foreground=[("selected", ACTIVE_TEXT), ("active", TEXT)],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground=ACTIVE_TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(12, 6),
        font=small_bold,
    )
    style.configure(
        "Soft.TButton",
        background=BG3,
        foreground=TEXT,
        borderwidth=0,
        focusthickness=0,
        padding=(10, 5),
        font=base_font,
    )
    style.map(
        "Soft.TButton",
        background=[("active", SURFACE_HOVER), ("pressed", BORDER)],
        foreground=[("active", TEXT)],
    )
