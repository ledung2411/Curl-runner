# ui_compare.py — Popup so sánh n nội dung side-by-side với highlight diff
# type: ignore
from __future__ import annotations

import re
import json
import shlex
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font as tkfont
from typing import TYPE_CHECKING, Any

from constants import (
    BG, BG2, BG3, BORDER, ACCENT, TEXT, TEXT_DIM,
    ACTIVE_TEXT,
    GREEN, RED_C, YELLOW_C,
    SURFACE_HOVER, SURFACE_ACTIVE, TITLEBAR_BG, FONT_FAMILY, FONT_FAMILY_MONO,
)
from ui_theme import apply_modern_theme

if TYPE_CHECKING:
    from app import CurlRunnerApp


class CurlCompareWindow(tk.Toplevel):
    """
    Popup so sánh n nội dung side-by-side.
    - Mỗi panel có thể kéo thả resize (PanedWindow dọc)
    - Hỗ trợ Curl / JSON / Text / String
    - Thêm / xóa panel động
    """

    # Diff highlight colors
    HL_ADDED   = "#e9f8ef"
    HL_CHANGED = "#fff5d6"
    HL_SAME    = BG2
    HL_MISSING = "#f1f3f7"
    FG_ADDED   = "#18794e"
    FG_CHANGED = "#946200"
    FG_MISSING = "#8b95a5"
    RENDER_BATCH_ROWS = 250
    SEARCH_HIGHLIGHT_LIMIT = 5000

    def __init__(self, parent: "CurlRunnerApp", initial_curls: list[str] | None = None):
        super().__init__(parent)
        self.parent_app = parent
        self.title("⇄ So Sánh")
        self.geometry("1300x780")
        self.minsize(800, 500)
        self.configure(bg=BG)
        apply_modern_theme(self)

        self._panels: list[dict] = []
        self.mode_var = tk.StringVar(value="auto")
        self._compare_job_id = 0
        self._rendering = False
        self._compare_queue: queue.Queue = queue.Queue()
        self.compare_btn: tk.Button | None = None
        self.search_var = tk.StringVar()
        self.search_scope_var = tk.StringVar(value="All panels")
        self.search_case_var = tk.BooleanVar(value=False)
        self.search_only_var = tk.BooleanVar(value=False)
        self.search_after: str | None = None
        self.search_matches: list[tuple[int, str, str]] = []
        self.search_match_index = -1
        self.search_match_overflow = False
        self.search_entry: tk.Entry | None = None
        self.search_scope_cb: ttk.Combobox | None = None
        self.search_count_lbl: tk.Label | None = None
        self._last_mode = ""
        self._last_labels: list[str] = []
        self._last_diff_results: list[list[tuple]] = []
        self._display_filter_key: tuple | None = None
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

        tk.Label(tb, text="⇄  So Sánh",
                 font=tkfont.Font(family=FONT_FAMILY, size=13, weight="bold"),
                 bg=TITLEBAR_BG, fg=TEXT).pack(side="left", padx=14, pady=10)

        self._mkbtn(tb, "＋ Thêm panel", self._add_panel,      side="left", pad=(4, 0))
        self.compare_btn = self._mkbtn(tb, "⇄ So sánh", self._run_compare, side="left", pad=(6, 0))
        self._mkbtn(tb, "📋 Từ tab mở",  self._load_from_tabs, side="left", pad=(6, 0))

        mode_box = tk.Frame(tb, bg=TITLEBAR_BG)
        mode_box.pack(side="left", padx=(12, 0))
        tk.Label(mode_box, text="Mode:", font=self.fn_small,
                 bg=TITLEBAR_BG, fg=TEXT_DIM).pack(side="left", padx=(0, 4))
        mode_cb = ttk.Combobox(
            mode_box, textvariable=self.mode_var,
            values=("auto", "curl", "json", "text", "string"),
            state="readonly", width=9, font=self.fn_label,
        )
        mode_cb.pack(side="left")
        mode_cb.bind("<<ComboboxSelected>>", lambda _e: self._run_compare())

        # Search bar
        search = tk.Frame(self, bg=BG3)
        search.pack(fill="x", padx=12, pady=(6, 2))
        tk.Label(search, text="Search", font=self.fn_label,
                 bg=BG3, fg=TEXT_DIM).pack(side="left", padx=(8, 5))
        self.search_var.trace_add("write", self._schedule_compare_search)
        self.search_entry = tk.Entry(
            search, textvariable=self.search_var, font=self.fn_monos,
            bg=BG2, fg=TEXT, insertbackground=ACCENT, relief="flat",
            bd=0, width=24,
        )
        self.search_entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.search_entry.bind("<Return>", lambda _e: self._goto_compare_match(1))
        self.search_entry.bind("<Shift-Return>", lambda _e: self._goto_compare_match(-1))
        self.search_entry.bind("<Escape>", lambda _e: self._clear_compare_search())

        tk.Label(search, text="Scope:", font=self.fn_small,
                 bg=BG3, fg=TEXT_DIM).pack(side="left", padx=(8, 4))
        self.search_scope_cb = ttk.Combobox(
            search, textvariable=self.search_scope_var,
            values=("All panels",), state="readonly", width=22,
            font=self.fn_label,
        )
        self.search_scope_cb.pack(side="left")
        self.search_scope_cb.bind("<<ComboboxSelected>>", lambda _e: self._schedule_compare_search())

        self.search_count_lbl = tk.Label(search, text="", font=self.fn_small,
                                         bg=BG3, fg=TEXT_DIM, width=14)
        self.search_count_lbl.pack(side="left", padx=(6, 2))
        self._mkbtn(search, "Prev", lambda: self._goto_compare_match(-1), side="left", pad=(0, 2))
        self._mkbtn(search, "Next", lambda: self._goto_compare_match(1), side="left", pad=(0, 2))
        self._mkbtn(search, "Clear", self._clear_compare_search, side="left", pad=(0, 2))
        tk.Checkbutton(
            search, text="Aa", variable=self.search_case_var,
            command=self._schedule_compare_search,
            font=self.fn_small, bg=BG3, fg=TEXT_DIM,
            activebackground=BG3, activeforeground=TEXT,
            selectcolor=BG2, bd=0, padx=4,
        ).pack(side="left", padx=(0, 4))
        tk.Checkbutton(
            search, text="Only results", variable=self.search_only_var,
            command=self._schedule_compare_search,
            font=self.fn_small, bg=BG3, fg=TEXT_DIM,
            activebackground=BG3, activeforeground=TEXT,
            selectcolor=BG2, bd=0, padx=4,
        ).pack(side="left", padx=(0, 6))
        self.bind("<Control-f>", self._focus_compare_search)

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
        name = f"Panel {idx + 1}"

        outer = tk.Frame(self.paned, bg=BG)
        outer.pack_propagate(True)

        # Header
        hdr = tk.Frame(outer, bg=SURFACE_ACTIVE, height=34)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        label_var = tk.StringVar(value=name)
        lbl = tk.Label(hdr, textvariable=label_var, font=self.fn_label,
                       bg=SURFACE_ACTIVE, fg=ACTIVE_TEXT, cursor="hand2")
        lbl.pack(side="left", padx=8)
        lbl.bind("<Double-Button-1>", lambda e, lv=label_var: self._rename_panel(lv))

        diff_badge = tk.Label(hdr, text="", font=self.fn_small, bg=SURFACE_ACTIVE, fg=ACTIVE_TEXT)
        diff_badge.pack(side="left", padx=4)

        tk.Button(hdr, text="✕", font=self.fn_small,
                  bg=SURFACE_ACTIVE, fg=ACTIVE_TEXT, activebackground=RED_C,
                  activeforeground=ACTIVE_TEXT,
                  relief="flat", cursor="hand2", bd=0, padx=6,
                  command=lambda o=outer: self._remove_panel(o)).pack(side="right", padx=4)

        # Vertical pane: input (top) + diff view (bottom)
        vpane = tk.PanedWindow(outer, orient="vertical", bg=BORDER,
                               sashwidth=5, sashrelief="flat", bd=0)
        vpane.pack(fill="both", expand=True)

        # Input area
        inp_frame = tk.Frame(vpane, bg=BG2)
        tk.Label(inp_frame, text="INPUT  (curl / json / text / string)", font=self.fn_badge,
                 bg=BG2, fg=TEXT_DIM, anchor="w").pack(fill="x", padx=6, pady=(4, 0))

        inp_wrap = tk.Frame(inp_frame, bg=BORDER)
        inp_wrap.pack(fill="both", expand=True, padx=2, pady=2)
        inp_tw = tk.Text(inp_wrap, bg=BG2, fg=TEXT, font=self.fn_mono,
                         wrap="none", relief="flat", padx=8, pady=6,
                         insertbackground=ACCENT,
                         selectbackground=ACCENT, selectforeground=ACTIVE_TEXT,
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
                          cursor="xterm", bd=0)
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
        diff_tw.tag_configure("search_match", background="#ffe4d6", foreground=TEXT)
        diff_tw.tag_configure("search_current", background=ACCENT, foreground=ACTIVE_TEXT)
        diff_tw.tag_raise("search_current")
        self._make_diff_text_copyable(diff_tw)

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
        self._refresh_search_scope_options()
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
        self._refresh_search_scope_options()
        self._clear_compare_search_tags()
        self._run_compare()

    def _rename_panel(self, label_var: tk.StringVar) -> None:
        new = simpledialog.askstring("Đổi tên", "Tên panel:",
                                     initialvalue=label_var.get(), parent=self)
        if new and new.strip():
            label_var.set(new.strip())
            self._refresh_search_scope_options()
            self._schedule_compare_search()

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
        self._refresh_search_scope_options()
        self._run_compare()

    # ── Search ────────────────────────────────
    def _panel_scope_label(self, idx: int, panel: dict) -> str:
        return f"#{idx + 1} {panel['label_var'].get()}"

    def _refresh_search_scope_options(self) -> None:
        if not self.search_scope_cb:
            return
        current = self.search_scope_var.get()
        values = ["All panels"] + [
            self._panel_scope_label(idx, panel)
            for idx, panel in enumerate(self._panels)
        ]
        self.search_scope_cb.configure(values=values)
        if current not in values:
            self.search_scope_var.set("All panels")

    def _search_target_indices(self) -> list[int]:
        scope = self.search_scope_var.get()
        if scope == "All panels":
            return list(range(len(self._panels)))
        match = re.match(r"#(\d+)\s", scope)
        if not match:
            return list(range(len(self._panels)))
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(self._panels):
            return [idx]
        return list(range(len(self._panels)))

    def _search_terms(self) -> list[str]:
        raw = self.search_var.get()
        if "|" not in raw:
            return [raw] if raw else []
        return [part.strip() for part in raw.split("|") if part.strip()]

    def _search_display_key(self, terms: list[str]) -> tuple | None:
        if not self.search_only_var.get() or not terms:
            return None
        return (
            tuple(term.lower() if not self.search_case_var.get() else term for term in terms),
            tuple(self._search_target_indices()),
            self.search_case_var.get(),
        )

    def _text_matches_terms(self, text: str, terms: list[str]) -> bool:
        if self.search_case_var.get():
            return any(term in text for term in terms)
        lowered = text.lower()
        return any(term.lower() in lowered for term in terms)

    def _sync_search_only_view(self, terms: list[str]) -> None:
        desired_key = self._search_display_key(terms)
        if desired_key == self._display_filter_key:
            return
        if not self._last_diff_results:
            self._display_filter_key = desired_key
            return

        if desired_key is None:
            self._render_diff_results_now(self._last_diff_results, filtered=False)
            self._display_filter_key = None
            return

        target_indices = set(self._search_target_indices())
        filtered_results: list[list[tuple]] = []
        for panel_idx, panel_diff in enumerate(self._last_diff_results):
            if panel_idx not in target_indices:
                filtered_results.append([])
                continue
            filtered_results.append([
                (text, tag)
                for text, tag in panel_diff
                if self._text_matches_terms(text, terms)
            ])
        self._render_diff_results_now(filtered_results, filtered=True)
        self._display_filter_key = desired_key

    def _render_diff_results_now(self, diff_results: list[list[tuple]], filtered: bool) -> None:
        total_visible = 0
        for panel_idx, panel in enumerate(self._panels):
            panel_diff = diff_results[panel_idx] if panel_idx < len(diff_results) else []
            total_visible += len(panel_diff)
            tw = panel["diff_tw"]
            tw.config(state="normal")
            tw.delete("1.0", "end")
            for row_idx, (text, tag) in enumerate(panel_diff, 1):
                tw.insert("end", f"{row_idx:>6}  ", "linenum")
                tw.insert("end", (text or "·" * 30) + "\n", tag)
            tw.config(state="normal")

            if filtered:
                panel["diff_badge"].config(
                    text=f"  {len(panel_diff)} search results",
                    fg=GREEN if panel_diff else TEXT_DIM,
                )

        if filtered:
            scope = self.search_scope_var.get()
            self.result_lbl.config(
                text=f"  Search filter: {total_visible} dòng match  ·  Scope: {scope}",
                fg=TEXT_DIM,
            )
        elif self._last_diff_results:
            total = len(self._last_diff_results[0]) if self._last_diff_results else 0
            same = sum(1 for _, tag in self._last_diff_results[0] if tag == "same")
            self.result_lbl.config(
                text=f"  Mode: {self._last_mode}  ·  {len(self._last_labels)} panels  ·  {total} dòng  ·  "
                     f"{same} giống  ·  {total - same} khác  ·  full input, no character limit",
                fg=TEXT_DIM,
            )

    def _focus_compare_search(self, _event=None):
        if self.search_entry:
            self.search_entry.focus_set()
            self.search_entry.selection_range(0, "end")
        return "break"

    def _clear_compare_search(self):
        self.search_var.set("")
        self.search_matches = []
        self.search_match_index = -1
        self.search_match_overflow = False
        self._clear_compare_search_tags()
        self._update_compare_search_count()
        return "break"

    def _schedule_compare_search(self, *_):
        if not self.search_count_lbl:
            return
        if self.search_after:
            self.after_cancel(self.search_after)
        self.search_after = self.after(120, self._run_compare_search)

    def _clear_compare_search_tags(self, widget: tk.Text | None = None) -> None:
        widgets = [widget] if widget else [
            panel["diff_tw"] for panel in self._panels if panel.get("diff_tw")
        ]
        for tw in widgets:
            old_state = str(tw.cget("state"))
            if old_state == "disabled":
                tw.config(state="normal")
            tw.tag_remove("search_match", "1.0", "end")
            tw.tag_remove("search_current", "1.0", "end")
            if old_state == "disabled":
                tw.config(state="disabled")

    def _reset_compare_search_results(self, clear_tags: bool = True) -> None:
        self.search_matches = []
        self.search_match_index = -1
        self.search_match_overflow = False
        if clear_tags:
            self._clear_compare_search_tags()
        self._update_compare_search_count(rendering=self._rendering and bool(self._search_terms()))

    def _run_compare_search(self) -> None:
        self.search_after = None
        terms = self._search_terms()
        self.search_matches = []
        self.search_match_index = -1
        self.search_match_overflow = False
        self._sync_search_only_view(terms)
        self._clear_compare_search_tags()

        if not terms:
            self._update_compare_search_count()
            return
        if self._rendering:
            self._update_compare_search_count(rendering=True)
            return

        target_indices = self._search_target_indices()
        nocase = 0 if self.search_case_var.get() else 1
        count_var = tk.IntVar(self)
        matches: list[tuple[int, str, str]] = []
        overflow = False

        for panel_idx in target_indices:
            if panel_idx >= len(self._panels):
                continue
            tw = self._panels[panel_idx]["diff_tw"]
            old_state = str(tw.cget("state"))
            if old_state == "disabled":
                tw.config(state="normal")

            panel_matches: list[tuple[int, str, str]] = []
            seen: set[tuple[str, str]] = set()
            for term in terms:
                pos = "1.0"
                while len(matches) + len(panel_matches) < self.SEARCH_HIGHLIGHT_LIMIT:
                    hit = tw.search(term, pos, "end", nocase=nocase, count=count_var)
                    if not hit:
                        break
                    chars = count_var.get() or len(term)
                    end = f"{hit}+{chars}c"
                    key = (hit, end)
                    if key not in seen:
                        seen.add(key)
                        panel_matches.append((panel_idx, hit, end))
                    pos = end if chars > 0 else f"{hit}+1c"
                if len(matches) + len(panel_matches) >= self.SEARCH_HIGHLIGHT_LIMIT:
                    break

            panel_matches.sort(key=lambda item: (tw.count("1.0", item[1], "chars") or (0,))[0])
            for _panel_idx, start, end in panel_matches:
                tw.tag_add("search_match", start, end)
            matches.extend(panel_matches)

            tw.tag_raise("search_match")
            tw.tag_raise("search_current")
            if old_state == "disabled":
                tw.config(state="disabled")
            if len(matches) >= self.SEARCH_HIGHLIGHT_LIMIT:
                overflow = True
                break

        self.search_matches = matches
        self.search_match_overflow = overflow
        if matches:
            self.search_match_index = 0
            self._mark_compare_current()
        else:
            self._update_compare_search_count()

    def _goto_compare_match(self, step: int):
        if not self._search_terms():
            return self._focus_compare_search()
        if self._rendering:
            self._update_compare_search_count(rendering=True)
            return "break"
        if not self.search_matches:
            self._run_compare_search()
        if not self.search_matches:
            return "break"
        if self.search_match_index < 0:
            self.search_match_index = 0
        else:
            self.search_match_index = (self.search_match_index + step) % len(self.search_matches)
        self._mark_compare_current()
        return "break"

    def _mark_compare_current(self) -> None:
        if not self.search_matches:
            self._update_compare_search_count()
            return
        for panel in self._panels:
            tw = panel["diff_tw"]
            old_state = str(tw.cget("state"))
            if old_state == "disabled":
                tw.config(state="normal")
            tw.tag_remove("search_current", "1.0", "end")
            if old_state == "disabled":
                tw.config(state="disabled")

        panel_idx, start, end = self.search_matches[self.search_match_index]
        if panel_idx >= len(self._panels):
            self._run_compare_search()
            return
        tw = self._panels[panel_idx]["diff_tw"]
        old_state = str(tw.cget("state"))
        if old_state == "disabled":
            tw.config(state="normal")
        tw.tag_add("search_current", start, end)
        tw.tag_raise("search_current")
        if old_state == "disabled":
            tw.config(state="disabled")
        tw.see(start)
        self._update_compare_search_count()

    def _update_compare_search_count(self, rendering: bool = False) -> None:
        if not self.search_count_lbl:
            return
        if not self._search_terms():
            self.search_count_lbl.config(text="")
        elif rendering:
            self.search_count_lbl.config(text="rendering...")
        elif not self.search_matches:
            self.search_count_lbl.config(text="0/0")
        else:
            panel_idx = self.search_matches[self.search_match_index][0]
            total = f"{len(self.search_matches)}+" if self.search_match_overflow else str(len(self.search_matches))
            self.search_count_lbl.config(text=f"{self.search_match_index + 1}/{total}  P{panel_idx + 1}")

    # ── Diff engine ───────────────────────────
    def _detect_mode(self, raws: list[str], explicit: str = "auto") -> str:
        explicit = (explicit or "auto").strip().lower()
        if explicit != "auto":
            return explicit

        nonempty = [raw.strip() for raw in raws if raw.strip()]
        if not nonempty:
            return "text"
        if all(raw.lower().startswith("curl ") or raw.lower() == "curl" for raw in nonempty):
            return "curl"
        if all(self._try_json(raw) is not None for raw in nonempty):
            return "json"
        if all("\n" not in raw and len(raw) <= 500 for raw in nonempty):
            return "string"
        return "text"

    def _try_json(self, raw: str) -> Any:
        try:
            return json.loads(raw)
        except Exception:
            return None

    def _normalize_input(self, raw: str, mode: str) -> list[str]:
        if mode == "curl":
            return self._normalize_curl(raw)
        if mode == "json":
            return self._normalize_json(raw)
        if mode == "string":
            return self._normalize_string(raw)
        return self._normalize_text(raw)

    def _normalize_text(self, raw: str) -> list[str]:
        return raw.splitlines() or ([raw] if raw else [])

    def _normalize_string(self, raw: str) -> list[str]:
        text = raw.strip()
        if not text:
            return []
        tokens = re.findall(r"\S+", text)
        if len(tokens) > 1:
            return [f"{idx:03}: {token}" for idx, token in enumerate(tokens, 1)]
        # Long single-token strings are compared in fixed blocks to avoid creating
        # one UI row per character. This does not truncate the input.
        chunk = 96
        return [
            f"{(idx // chunk) + 1:06}: {text[idx:idx + chunk]}"
            for idx in range(0, len(text), chunk)
        ]

    def _normalize_json(self, raw: str) -> list[str]:
        data = self._try_json(raw)
        if data is None:
            return ["[Invalid JSON]"] + self._normalize_text(raw)
        lines: list[str] = []

        def walk(value: Any, path: str) -> None:
            if isinstance(value, dict):
                if not value:
                    lines.append(f"{path}: {{}}")
                for key in sorted(value.keys(), key=str):
                    child_path = f"{path}.{key}" if path else str(key)
                    walk(value[key], child_path)
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{path}: []")
                for idx, item in enumerate(value):
                    child_path = f"{path}[{idx}]" if path else f"[{idx}]"
                    walk(item, child_path)
            else:
                rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
                lines.append(f"{path or '$'}: {rendered}")

        walk(data, "$")
        return lines

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
                i += 1
                if ":" in tokens[i]:
                    key, _, value = tokens[i].partition(":")
                    parts.append(f"Header.{key.strip()}: {value.strip()}")
                else:
                    parts.append(f"Header: {tokens[i]}")
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
                i += 1
                if "=" in tokens[i]:
                    key, _, value = tokens[i].partition("=")
                    parts.append(f"Form.{key}: {value}")
                else:
                    parts.append(f"Form: {tokens[i]}")
            i += 1

        return [f"Method: {method}", f"URL: {url}"] + sorted(parts)

    def _compute_keyed_diff(self, panels_lines: list[list[str]]) -> list[list[tuple]]:
        """Align semantic lines by key/path before comparing values."""
        n = len(panels_lines)
        results: list[list[tuple]] = [[] for _ in range(n)]
        rows_by_panel: list[dict[str, str]] = []
        ordered_keys: list[str] = []

        for lines in panels_lines:
            mapping: dict[str, str] = {}
            for line in lines:
                key = line.partition(":")[0].strip() if ":" in line else line.strip()
                key = key or line
                if key not in mapping:
                    mapping[key] = line
                    if key not in ordered_keys:
                        ordered_keys.append(key)
            rows_by_panel.append(mapping)

        for key in ordered_keys:
            row_vals = [rows_by_panel[pi].get(key) for pi in range(n)]
            present = [v for v in row_vals if v is not None]
            all_same = len(set(present)) == 1
            missing_count = row_vals.count(None)
            majority = max(set(present), key=present.count) if present else None
            for pi, val in enumerate(row_vals):
                if val is None:
                    results[pi].append((f"{key}: (missing)", "missing"))
                elif all_same:
                    results[pi].append((val, "added" if missing_count else "same"))
                elif missing_count and present.count(val) == 1:
                    results[pi].append((val, "added"))
                elif val == majority and present.count(val) > 1:
                    results[pi].append((val, "same"))
                else:
                    results[pi].append((val, "changed"))
        return results

    def _compute_line_diff(self, panels_lines: list[list[str]]) -> list[list[tuple]]:
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
            counts = {v: present.count(v) for v in set(present)}

            for pi, val in enumerate(row_vals):
                if val is None:
                    results[pi].append(("", "missing"))
                elif all_same:
                    results[pi].append((val, "same"))
                else:
                    majority = max(set(present), key=present.count)
                    if val == majority and counts.get(val, 0) > 1:
                        tag = "same"
                    elif counts.get(val, 0) == 1:
                        tag = "added"
                    else:
                        tag = "changed"
                    results[pi].append((val, tag))

        return results

    def _run_compare(self) -> None:
        """Chạy diff engine ở background và render kết quả theo batch."""
        if not self._panels:
            return

        self._compare_job_id += 1
        job_id = self._compare_job_id
        raws = [p["inp_tw"].get("1.0", "end").strip() for p in self._panels]
        requested_mode = self.mode_var.get().strip().lower()
        labels = [p["label_var"].get() for p in self._panels]
        self._rendering = True
        self._last_mode = ""
        self._last_labels = []
        self._last_diff_results = []
        self._display_filter_key = None
        self._reset_compare_search_results()
        if self.compare_btn:
            self.compare_btn.config(state="disabled", text="Đang so sánh...")
        self.result_lbl.config(
            text=f"  Đang đọc {len(raws)} panel, xử lý background... Không giới hạn ký tự.",
            fg=TEXT_DIM,
        )
        for panel in self._panels:
            dw = panel["diff_tw"]
            dw.config(state="normal")
            dw.delete("1.0", "end")
            dw.insert("end", "  Đang xử lý...\n", "linenum")
            dw.config(state="normal")
            panel["diff_badge"].config(text="  working...", fg=TEXT_DIM)

        def worker() -> None:
            try:
                mode = self._detect_mode(raws, requested_mode)
                panels_lines = [self._normalize_input(raw, mode) or [] for raw in raws]
                if mode in ("curl", "json"):
                    diff_results = self._compute_keyed_diff(panels_lines)
                else:
                    diff_results = self._compute_line_diff(panels_lines)
                self._compare_queue.put((job_id, mode, labels, diff_results, None))
            except Exception as exc:
                msg = str(exc) or exc.__class__.__name__
                self._compare_queue.put((job_id, "error", labels, [], msg))

        threading.Thread(target=worker, daemon=True).start()
        self.after(50, lambda: self._poll_compare_queue(job_id))

    def _poll_compare_queue(self, job_id: int) -> None:
        if job_id != self._compare_job_id:
            return
        try:
            while True:
                result_job_id, mode, labels, diff_results, error = self._compare_queue.get_nowait()
                if result_job_id == self._compare_job_id:
                    self._start_render_compare(result_job_id, mode, labels, diff_results, error)
                    return
        except queue.Empty:
            pass
        self.after(50, lambda: self._poll_compare_queue(job_id))

    def _start_render_compare(
        self,
        job_id: int,
        mode: str,
        labels: list[str],
        diff_results: list[list[tuple]],
        error: str | None,
    ) -> None:
        if job_id != self._compare_job_id:
            return
        if error:
            self._rendering = False
            if self.compare_btn:
                self.compare_btn.config(state="normal", text="⇄ So sánh")
            self.result_lbl.config(text=f"  Compare failed: {error}", fg=RED_C)
            for panel in self._panels:
                dw = panel["diff_tw"]
                dw.config(state="normal")
                dw.delete("1.0", "end")
                dw.insert("end", error, "changed")
                dw.config(state="normal")
                panel["diff_badge"].config(text="  lỗi", fg=RED_C)
            return

        self._last_mode = mode
        self._last_labels = labels[:]
        self._last_diff_results = diff_results
        self._display_filter_key = None
        for pi, panel in enumerate(self._panels):
            dw = panel["diff_tw"]
            dw.config(state="normal")
            dw.delete("1.0", "end")
            dw.config(state="normal")
            panel["diff_badge"].config(text="  rendering...", fg=TEXT_DIM)

        same = sum(1 for _, tag in (diff_results[0] if diff_results else []) if tag == "same")
        total = len(diff_results[0]) if diff_results else 0
        self.result_lbl.config(
            text=f"  Mode: {mode}  ·  {len(labels)} panels  ·  {total} dòng  ·  "
                 f"{same} giống  ·  {total - same} khác  ·  đang render theo batch...",
            fg=TEXT_DIM,
        )
        self._render_compare_panel(job_id, mode, labels, diff_results, 0, 0)

    def _render_compare_panel(
        self,
        job_id: int,
        mode: str,
        labels: list[str],
        diff_results: list[list[tuple]],
        panel_idx: int,
        row_idx: int,
    ) -> None:
        if job_id != self._compare_job_id:
            return
        if panel_idx >= len(self._panels) or panel_idx >= len(diff_results):
            self._finish_render_compare(job_id, mode, labels, diff_results)
            return

        panel = self._panels[panel_idx]
        panel_diff = diff_results[panel_idx]
        dw = panel["diff_tw"]
        end = min(row_idx + self.RENDER_BATCH_ROWS, len(panel_diff))
        dw.config(state="normal")
        for ln in range(row_idx, end):
            text, tag = panel_diff[ln]
            dw.insert("end", f"{ln + 1:>6}  ", "linenum")
            dw.insert("end", (text or "·" * 30) + "\n", tag)
        dw.config(state="normal")

        rendered = end
        total = len(panel_diff)
        panel["diff_badge"].config(text=f"  render {rendered}/{total}", fg=TEXT_DIM)
        self.result_lbl.config(
            text=f"  Mode: {mode}  ·  rendering panel {panel_idx + 1}/{len(self._panels)} "
                 f"({rendered}/{total} rows)...",
            fg=TEXT_DIM,
        )

        if end < total:
            self.after(1, lambda: self._render_compare_panel(
                job_id, mode, labels, diff_results, panel_idx, end
            ))
        else:
            diff_count = sum(1 for _, tag in panel_diff if tag != "same")
            panel["diff_badge"].config(
                text=f"  {diff_count} khác biệt" if diff_count else "  ✓ Giống",
                fg=YELLOW_C if diff_count else GREEN,
            )
            self.after(1, lambda: self._render_compare_panel(
                job_id, mode, labels, diff_results, panel_idx + 1, 0
            ))

    def _finish_render_compare(
        self,
        job_id: int,
        mode: str,
        labels: list[str],
        diff_results: list[list[tuple]],
    ) -> None:
        if job_id != self._compare_job_id:
            return
        self._rendering = False
        if self.compare_btn:
            self.compare_btn.config(state="normal", text="⇄ So sánh")
        same = sum(1 for _, tag in (diff_results[0] if diff_results else []) if tag == "same")
        total = len(diff_results[0]) if diff_results else 0
        self.result_lbl.config(
            text=f"  Mode: {mode}  ·  {len(labels)} panels  ·  {total} dòng  ·  "
                 f"{same} giống  ·  {total - same} khác  ·  full input, no character limit",
            fg=TEXT_DIM,
        )
        if self.search_var.get():
            self._schedule_compare_search()

    # ── Helpers ───────────────────────────────
    def _make_diff_text_copyable(self, tw: tk.Text) -> None:
        tw.bind("<KeyPress>", self._block_diff_text_edit, add="+")
        tw.bind("<Control-a>", lambda _e, w=tw: self._select_all_diff_text(w))
        tw.bind("<Control-A>", lambda _e, w=tw: self._select_all_diff_text(w))
        tw.bind("<Control-c>", lambda _e, w=tw: self._copy_diff_selection(w))
        tw.bind("<Control-C>", lambda _e, w=tw: self._copy_diff_selection(w))
        tw.bind("<Control-v>", lambda _e: "break")
        tw.bind("<Control-V>", lambda _e: "break")
        tw.bind("<Control-x>", lambda _e: "break")
        tw.bind("<Control-X>", lambda _e: "break")
        tw.bind("<<Paste>>", lambda _e: "break")
        tw.bind("<<Cut>>", lambda _e: "break")
        tw.bind("<Button-2>", lambda _e: "break")
        tw.bind("<Button-3>", lambda e, w=tw: self._show_diff_context_menu(w, e))

    def _block_diff_text_edit(self, event) -> str | None:
        ctrl_pressed = bool(event.state & 0x4)
        nav_keys = {
            "Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End",
            "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
            "Escape",
        }
        if ctrl_pressed or event.keysym in nav_keys:
            return None
        return "break"

    def _select_all_diff_text(self, tw: tk.Text):
        tw.focus_set()
        tw.tag_add("sel", "1.0", "end-1c")
        tw.mark_set("insert", "1.0")
        tw.see("insert")
        return "break"

    def _copy_diff_selection(self, tw: tk.Text):
        try:
            selected = tw.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        if selected:
            self.clipboard_clear()
            self.clipboard_append(selected)
        return "break"

    def _copy_all_diff_text(self, tw: tk.Text):
        content = tw.get("1.0", "end-1c")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
        return "break"

    def _show_diff_context_menu(self, tw: tk.Text, event):
        tw.focus_set()
        menu = tk.Menu(self, tearoff=0, bg=BG3, fg=TEXT, activebackground=ACCENT)
        menu.add_command(label="Copy", command=lambda: self._copy_diff_selection(tw))
        menu.add_command(label="Select all", command=lambda: self._select_all_diff_text(tw))
        menu.add_command(label="Copy all", command=lambda: self._copy_all_diff_text(tw))
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _mkbtn(self, parent: tk.Widget, text: str, cmd,
               side: str = "left", pad: tuple = (0, 0)) -> tk.Button:
        b = tk.Button(parent, text=text, font=self.fn_label,
                      bg=BG3, fg=TEXT, activebackground=SURFACE_HOVER,
                      activeforeground=TEXT,
                      relief="flat", cursor="hand2",
                      padx=10, pady=5, command=cmd, bd=0)
        b.bind("<Enter>", lambda _e: b.config(bg=SURFACE_HOVER) if str(b["state"]) == "normal" else None)
        b.bind("<Leave>", lambda _e: b.config(bg=BG3) if str(b["state"]) == "normal" else None)
        b.pack(side=side, padx=pad)
        return b
