# ui_widgets.py — Widget helpers dùng chung toàn app
# type: ignore
import tkinter as tk
from tkinter import font as tkfont
from constants import (
    BG, BG3, BORDER, TEXT, TEXT_DIM, ACCENT, FONT_FAMILY, FONT_FAMILY_MONO,
)


def make_button(parent: tk.Widget, text: str, cmd,
                font: tkfont.Font,
                side: str = "left",
                pad: tuple[int, int] = (0, 0)) -> tk.Button:
    """Button theo style dark theme của app."""
    b = tk.Button(parent, text=text, font=font,
                  bg=BG3, fg=TEXT, activebackground=BORDER,
                  relief="flat", cursor="hand2",
                  padx=10, pady=4, command=cmd, bd=0)
    b.pack(side=side, padx=pad)
    return b


def make_scrolled_text(parent: tk.Widget,
                       font: tkfont.Font,
                       state: str = "normal",
                       wrap: str = "word",
                       horizontal_scroll: bool = False) -> tuple[tk.Frame, tk.Text]:
    """
    Tạo tk.Text có scrollbar, bọc trong Frame.
    Returns (wrap_frame, text_widget)
    """
    from constants import BG2, BG3, BORDER, ACCENT

    wrap_frame = tk.Frame(parent, bg=BORDER)
    tw = tk.Text(wrap_frame, bg=BG2, fg=TEXT, font=font,
                 wrap=wrap, relief="flat", padx=10, pady=8,
                 insertbackground=ACCENT,
                 selectbackground=ACCENT, selectforeground="#fff",
                 state=state, bd=0, undo=True)

    sb_y = tk.Scrollbar(wrap_frame, command=tw.yview,
                        bg=BG3, troughcolor=BG2, bd=0)
    tw.configure(yscrollcommand=sb_y.set)
    sb_y.pack(side="right", fill="y")

    if horizontal_scroll:
        sb_x = tk.Scrollbar(wrap_frame, orient="horizontal",
                             command=tw.xview, bg=BG3, troughcolor=BG2, bd=0)
        tw.configure(xscrollcommand=sb_x.set)
        sb_x.pack(side="bottom", fill="x")

    tw.pack(fill="both", expand=True, padx=1, pady=1)
    return wrap_frame, tw


def make_section_label(parent: tk.Widget, text: str,
                       font: tkfont.Font,
                       side: str = "top") -> tk.Label:
    """Label nhỏ dạng badge/header."""
    lbl = tk.Label(parent, text=text, font=font, bg=BG, fg=TEXT_DIM)
    if side == "top":
        lbl.pack(anchor="w", pady=(0, 4))
    else:
        lbl.pack(side=side, padx=(0, 8))
    return lbl


def make_checkbox(parent: tk.Widget, text: str,
                  var: tk.BooleanVar,
                  font: tkfont.Font) -> tk.Checkbutton:
    """Checkbox theo style dark theme."""
    from constants import BG3
    cb = tk.Checkbutton(parent, text=text, variable=var,
                        font=font, bg=BG, fg=TEXT_DIM,
                        activebackground=BG, selectcolor=BG3,
                        relief="flat", bd=0)
    cb.pack(side="left", padx=(0, 8))
    return cb
