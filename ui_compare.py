# ui_compare.py — Popup so sánh n curl side-by-side với highlight diff
# type: ignore
from __future__ import annotations

import re
import json
import shlex
import tkinter as tk
from tkinter import messagebox, simpledialog, font as tkfont
from typing import TYPE_CHECKING

from constants import (
    BG, BG2, BG3, BORDER, ACCENT, TEXT, TEXT_DIM,
    GREEN, RED_C, YELLOW_C,
    SURFACE_ACTIVE, TITLEBAR_BG, FONT_FAMILY, FONT_FAMILY_MONO,
)

if TYPE_CHECKING:
    from app import CurlRunnerApp


class CurlCompareWindow(tk.Toplevel):
    """
    Popup so sánh n curl command side-by-side.
    - Mỗi panel có thể kéo thả resize (PanedWindow dọc)
    - Highlight diff theo line-level semantic
    - Thêm / xóa panel động
    """

    # Diff highlight colors
    HL_ADDED   = "#1e3a1e"
    HL_CHANGED = "#3a2e10"
    HL_SAME    = BG2
    HL_MISSING = "#2a1a1a"
    FG_ADDED   = "#6fcf6f"
    FG_CHANGED = "#f0c060"
    FG_MISSING = "#555b70"

    def __init__(self, parent: "CurlRunnerApp", initial_curls: list[str] | None = None):
        super().__init__(parent)
        self.parent_app = parent
        self.title("⇄ So Sánh Curl")
        self.geometry("1300x780")
        self.minsize(800, 500)
        self.configure(bg=BG)

        self._panels: list[dict] = []
        self._setup_fonts()
        self._build_ui()

        seeds = initial_curls or ["", ""]
        for c in seeds:
            self._add_panel(c)
        self._run_compare()

    # ── Fonts ─────────────────────────────────
    def _setup_fonts(self) -> None:
        self.fn_mono  = tkfont.Font(family=FONT_FAMILY_MONO, size=10)
        self.fn_monos = tkfont.Font(family=FONT_FAMILY_MONO, size=9)
        self.fn_label = tkfont.Font(family=FONT_FAMILY, size=9)
        self.fn_btn   = tkfont.Font(family=FONT_FAMILY, size=9, weight="bold")
        self.fn_badge = tkfont.Font(family=FONT_FAMILY, size=8, weight="bold")
        self.fn_small = tkfont.Font(family=FONT_FAMILY, size=8)

    # ── Layout ────────────────────────────────
    def _build_ui(self) -> None:
        # Toolbar
        tb = tk.Frame(self, bg=TITLEBAR_BG, height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        tk.Label(tb, text="⇄  So Sánh Curl",
                 font=tkfont.Font(family=FONT_FAMILY, size=13, weight="bold"),
                 bg=TITLEBAR_BG, fg=TEXT).pack(side="left", padx=14, pady=10)

        self._mkbtn(tb, "＋ Thêm panel", self._add_panel,      side="left", pad=(4, 0))
        self._mkbtn(tb, "⇄ So sánh",     self._run_compare,    side="left", pad=(6, 0))
        self._mkbtn(tb, "📋 Từ tab mở",  self._load_from_tabs, side="left", pad=(6, 0))

        tk.Label(tb, text="Double-click tên để đổi  ·  Kéo thanh phân cách để resize",
                 font=tkfont.Font(family=FONT_FAMILY, size=8),
                 bg=TITLEBAR_BG, fg=TEXT_DIM).pack(side="right", padx=14)

        # Legend
        leg = tk.Frame(self, bg=BG)
        leg.pack(fill="x", padx=12, pady=(4, 2))
        for color, fg, label in [
            (self.HL_ADDED,   self.FG_ADDED,   "● Chỉ có ở panel này"),
            (self.HL_CHANGED, self.FG_CHANGED, "● Khác biệt"),
            (self.HL_MISSING, self.FG_MISSING, "● Dòng trống (align)"),
            (self.HL_SAME,    TEXT,             "  Giống nhau"),
        ]:
            tk.Label(leg, text=label, font=self.fn_small,
                     bg=color, fg=fg, padx=6, pady=1).pack(side="left", padx=(0, 6))

        # Summary label
        self.result_lbl = tk.Label(self, text="", font=self.fn_small,
                                   bg=BG, fg=TEXT_DIM, anchor="w")
        self.result_lbl.pack(fill="x", padx=14, pady=(0, 2))

        # Main paned window (horizontal)
        self.paned = tk.PanedWindow(self, orient="horizontal", bg=BORDER,
                                    sashwidth=6, sashrelief="flat", sashpad=2, bd=0)
        self.paned.pack(fill="both", expand=True, padx=4, pady=(0, 6))

    # ── Panel management ──────────────────────
    def _add_panel(self, curl_text: str = "") -> dict:
        idx  = len(self._panels)
        name = f"Curl {idx + 1}"

        outer = tk.Frame(self.paned, bg=BG)
        outer.pack_propagate(True)

        # Header
        hdr = tk.Frame(outer, bg=SURFACE_ACTIVE, height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        label_var = tk.StringVar(value=name)
        lbl = tk.Label(hdr, textvariable=label_var, font=self.fn_label,
                       bg=SURFACE_ACTIVE, fg="white", cursor="hand2")
        lbl.pack(side="left", padx=8)
        lbl.bind("<Double-Button-1>", lambda e, lv=label_var: self._rename_panel(lv))

        diff_badge = tk.Label(hdr, text="", font=self.fn_small, bg=SURFACE_ACTIVE, fg="white")
        diff_badge.pack(side="left", padx=4)

        tk.Button(hdr, text="✕", font=self.fn_small,
                  bg=SURFACE_ACTIVE, fg="white", activebackground=RED_C,
                  relief="flat", cursor="hand2", bd=0, padx=6,
                  command=lambda o=outer: self._remove_panel(o)).pack(side="right", padx=4)

        # Vertical pane: input (top) + diff view (bottom)
        vpane = tk.PanedWindow(outer, orient="vertical", bg=BORDER,
                               sashwidth=5, sashrelief="flat", bd=0)
        vpane.pack(fill="both", expand=True)

        # Input area
        inp_frame = tk.Frame(vpane, bg=BG2)
        tk.Label(inp_frame, text="INPUT", font=self.fn_badge,
                 bg=BG2, fg=TEXT_DIM, anchor="w").pack(fill="x", padx=6, pady=(4, 0))

        inp_wrap = tk.Frame(inp_frame, bg=BORDER)
        inp_wrap.pack(fill="both", expand=True, padx=2, pady=2)
        inp_tw = tk.Text(inp_wrap, bg=BG2, fg=TEXT, font=self.fn_mono,
                         wrap="none", relief="flat", padx=8, pady=6,
                         insertbackground=ACCENT,
                         selectbackground=ACCENT, selectforeground="#fff",
                         undo=True, bd=0)
        sb_x = tk.Scrollbar(inp_wrap, orient="horizontal",
                             command=inp_tw.xview, bg=BG3, troughcolor=BG2, bd=0)
        sb_y = tk.Scrollbar(inp_wrap, command=inp_tw.yview,
                             bg=BG3, troughcolor=BG2, bd=0)
        inp_tw.configure(xscrollcommand=sb_x.set, yscrollcommand=sb_y.set)
        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        inp_tw.pack(fill="both", expand=True, padx=1, pady=1)
        if curl_text:
            inp_tw.insert("1.0", curl_text)
        vpane.add(inp_frame, minsize=80, height=200)

        # Diff view
        diff_frame = tk.Frame(vpane, bg=BG)
        tk.Label(diff_frame, text="DIFF VIEW", font=self.fn_badge,
                 bg=BG, fg=TEXT_DIM, anchor="w").pack(fill="x", padx=6, pady=(4, 0))

        diff_wrap = tk.Frame(diff_frame, bg=BORDER)
        diff_wrap.pack(fill="both", expand=True, padx=2, pady=2)
        diff_tw = tk.Text(diff_wrap, bg=BG2, fg=TEXT, font=self.fn_monos,
                          wrap="none", relief="flat", padx=8, pady=6,
                          state="disabled", bd=0)
        sb_dx = tk.Scrollbar(diff_wrap, orient="horizontal",
                              command=diff_tw.xview, bg=BG3, troughcolor=BG2, bd=0)
        sb_dy = tk.Scrollbar(diff_wrap, command=diff_tw.yview,
                              bg=BG3, troughcolor=BG2, bd=0)
        diff_tw.configure(xscrollcommand=sb_dx.set, yscrollcommand=sb_dy.set)
        sb_dy.pack(side="right", fill="y")
        sb_dx.pack(side="bottom", fill="x")
        diff_tw.pack(fill="both", expand=True, padx=1, pady=1)

        diff_tw.tag_configure("added",   background=self.HL_ADDED,   foreground=self.FG_ADDED)
        diff_tw.tag_configure("changed", background=self.HL_CHANGED, foreground=self.FG_CHANGED)
        diff_tw.tag_configure("missing", background=self.HL_MISSING, foreground=self.FG_MISSING)
        diff_tw.tag_configure("same",    background=self.HL_SAME,    foreground=TEXT)
        diff_tw.tag_configure("linenum", foreground=TEXT_DIM)

        vpane.add(diff_frame, minsize=80)
        self.paned.add(outer, minsize=250)

        panel = {
            "outer":      outer,
            "vpane":      vpane,
            "inp_tw":     inp_tw,
            "diff_tw":    diff_tw,
            "label_var":  label_var,
            "diff_badge": diff_badge,
        }
        self._panels.append(panel)
        return panel

    def _remove_panel(self, outer_frame: tk.Frame) -> None:
        if len(self._panels) <= 2:
            messagebox.showinfo("", "Cần ít nhất 2 panel để so sánh.")
            return
        idx = next((i for i, p in enumerate(self._panels)
                    if p["outer"] is outer_frame), None)
        if idx is None:
            return
        self.paned.remove(outer_frame)
        outer_frame.destroy()
        self._panels.pop(idx)
        self._run_compare()

    def _rename_panel(self, label_var: tk.StringVar) -> None:
        new = simpledialog.askstring("Đổi tên", "Tên panel:",
                                     initialvalue=label_var.get(), parent=self)
        if new and new.strip():
            label_var.set(new.strip())

    def _load_from_tabs(self) -> None:
        """Nạp curl từ các tab đang mở trong CurlRunnerApp."""
        open_curls: list[tuple[str, str]] = []
        for tab in self.parent_app.tabs:
            if tab._curl_tw is not None:
                curl = tab._curl_tw.get("1.0", "end").strip()
                if curl and not tab._ph_active:
                    open_curls.append((tab.name, curl))

        if not open_curls:
            messagebox.showinfo("", "Chưa có curl nào trong các tab đang mở.")
            return

        for p in list(self._panels):
            self.paned.remove(p["outer"])
            p["outer"].destroy()
        self._panels.clear()

        for name, curl in open_curls:
            p = self._add_panel(curl)
            p["label_var"].set(name)

        if len(self._panels) < 2:
            self._add_panel("")
        self._run_compare()

    # ── Diff engine ───────────────────────────
    def _normalize_curl(self, raw: str) -> list[str]:
        """
        Parse curl thành danh sách dòng 'KEY: value' chuẩn hóa
        để so sánh semantic (không phụ thuộc thứ tự flags).
        """
        s = re.sub(r'\\\s*\n\s*', ' ', raw)
        s = re.sub(r'\^\s*\n\s*', ' ', s).strip()
        try:
            tokens = shlex.split(s)
        except Exception:
            return raw.splitlines()
        if not tokens:
            return []

        method, url, parts = "GET", "", []
        i = 1
        while i < len(tokens):
            t = tokens[i]
            if not t.startswith('-') and not url:
                url = t
            elif t in ('-X', '--request') and i + 1 < len(tokens):
                i += 1; method = tokens[i].upper()
            elif t in ('-H', '--header') and i + 1 < len(tokens):
                i += 1; parts.append(f"Header: {tokens[i]}")
            elif t in ('-d', '--data', '--data-raw', '--data-binary', '--data-ascii') \
                    and i + 1 < len(tokens):
                i += 1
                try:
                    obj = json.loads(tokens[i])
                    for k, v in (obj.items() if isinstance(obj, dict) else []):
                        parts.append(f"Body.{k}: {json.dumps(v, ensure_ascii=False)}")
                except Exception:
                    parts.append(f"Body: {tokens[i]}")
            elif t in ('-u', '--user') and i + 1 < len(tokens):
                i += 1; parts.append(f"Auth: {tokens[i]}")
            elif t in ('-k', '--insecure'):
                parts.append("Option: insecure=true")
            elif t in ('-L', '--location'):
                parts.append("Option: follow-redirect=true")
            elif t in ('--max-time', '-m') and i + 1 < len(tokens):
                i += 1; parts.append(f"Option: timeout={tokens[i]}")
            elif t in ('-F', '--form') and i + 1 < len(tokens):
                i += 1; parts.append(f"Form: {tokens[i]}")
            i += 1

        return [f"Method: {method}", f"URL: {url}"] + sorted(parts)

    def _compute_diff(self, panels_lines: list[list[str]]) -> list[list[tuple]]:
        """
        So sánh n danh sách dòng.
        Returns list[panel_idx] → list[(line_text, tag)]
        tag: 'same' | 'changed' | 'missing'
        """
        if not panels_lines:
            return []
        n      = len(panels_lines)
        max_ln = max(len(p) for p in panels_lines)
        results: list[list[tuple]] = [[] for _ in range(n)]

        for row in range(max_ln):
            row_vals = [
                panels_lines[pi][row] if row < len(panels_lines[pi]) else None
                for pi in range(n)
            ]
            present  = [v for v in row_vals if v is not None]
            all_same = len(set(present)) == 1

            for pi, val in enumerate(row_vals):
                if val is None:
                    results[pi].append(("", "missing"))
                elif all_same:
                    results[pi].append((val, "same"))
                else:
                    majority = max(set(present), key=present.count)
                    tag = "same" if val == majority else "changed"
                    results[pi].append((val, tag))

        return results

    def _run_compare(self) -> None:
        """Chạy diff engine và render kết quả vào tất cả panels."""
        if not self._panels:
            return

        panels_lines = [
            self._normalize_curl(p["inp_tw"].get("1.0", "end").strip()) or []
            for p in self._panels
        ]
        diff_results = self._compute_diff(panels_lines)

        for pi, panel in enumerate(self._panels):
            dw = panel["diff_tw"]
            dw.config(state="normal")
            dw.delete("1.0", "end")

            if pi >= len(diff_results):
                dw.config(state="disabled")
                continue

            panel_diff = diff_results[pi]
            diff_count = sum(1 for _, tag in panel_diff if tag != "same")

            for ln, (text, tag) in enumerate(panel_diff, 1):
                dw.insert("end", f"{ln:>3}  ", "linenum")
                dw.insert("end", (text or "·" * 30) + "\n", tag)

            dw.config(state="disabled")
            panel["diff_badge"].config(
                text=f"  {diff_count} khác biệt" if diff_count else "  ✓ Giống",
                fg=YELLOW_C if diff_count else GREEN,
            )

        same  = sum(1 for _, tag in (diff_results[0] if diff_results else []) if tag == "same")
        total = len(diff_results[0]) if diff_results else 0
        self.result_lbl.config(
            text=f"  {len(self._panels)} panels  ·  {total} dòng  ·  "
                 f"{same} giống  ·  {total - same} khác"
        )

    # ── Helpers ───────────────────────────────
    def _mkbtn(self, parent: tk.Widget, text: str, cmd,
               side: str = "left", pad: tuple = (0, 0)) -> tk.Button:
        b = tk.Button(parent, text=text, font=self.fn_label,
                      bg=BG3, fg=TEXT, activebackground=BORDER,
                      relief="flat", cursor="hand2",
                      padx=10, pady=5, command=cmd, bd=0)
        b.pack(side=side, padx=pad)
        return b