#!/usr/bin/env python3
"""
curl_runner_gui.py — Curl Runner Desktop (v3)
Tính năng mới: Multi-tab · Pre-request Script · Beautify Body
Chạy  : python curl_runner_gui.py
Exe   : python -m PyInstaller --onefile --noconsole --name CurlRunner curl_runner_gui.py
"""

import sys, re, json, time, shlex, threading, os, uuid
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, font as tkfont

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from charset_normalizer import from_bytes as detect_encoding
    HAS_DETECT = True
except ImportError:
    try:
        from chardet import detect as _chardet_detect
        def detect_encoding(raw):
            class _R:
                best = type("B", (), {"encoding": _chardet_detect(raw).get("encoding","utf-8")})()
            return _R()
        HAS_DETECT = True
    except ImportError:
        HAS_DETECT = False

# ══════════════════════════════════════════════
# DATA STORE
# ══════════════════════════════════════════════
DATA_DIR  = Path(os.path.expanduser("~")) / ".curl_runner"
DATA_DIR.mkdir(exist_ok=True)
HIST_FILE = DATA_DIR / "history.json"
COLL_FILE = DATA_DIR / "collections.json"
ENV_FILE  = DATA_DIR / "environments.json"

def _load(path, default):
    try:    return json.loads(path.read_text(encoding="utf-8"))
    except: return default

def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ══════════════════════════════════════════════
# CORE LOGIC
# ══════════════════════════════════════════════
def apply_env(text: str, env: dict) -> str:
    for k, v in env.items():
        text = text.replace("{{" + k + "}}", v)
    return text

def run_pre_script(script: str, env: dict) -> tuple[dict, list[str]]:
    """
    Chạy pre-request script Python nhỏ.
    Script có thể dùng:
      env['token'] = '...'       → set biến env
      set_env('key', 'value')    → alias tiện hơn
      log('message')             → in ra console log
    Trả về (env_updated, logs)
    """
    logs   = []
    local_env = dict(env)

    def set_env(k, v):
        local_env[k] = str(v)
        logs.append(f"✓ set_env({k!r}, {str(v)[:40]!r})")

    def log(msg):
        logs.append(f"  {msg}")

    sandbox = {
        "env":     local_env,
        "set_env": set_env,
        "log":     log,
        "requests": requests,
        "json":    json,
        "re":      re,
    }
    try:
        exec(compile(script, "<pre-request>", "exec"), sandbox)
        # Sync back any direct env['key'] = val assignments
        for k, v in sandbox["env"].items():
            local_env[k] = v
        logs.insert(0, "✅ Script chạy thành công")
    except Exception as e:
        logs.insert(0, f"❌ Script lỗi: {e}")

    return local_env, logs

def parse_curl(curl_string: str) -> dict:
    curl_string = re.sub(r'\\\s*\n\s*', ' ', curl_string)
    curl_string = re.sub(r'\^\s*\n\s*', ' ', curl_string)
    curl_string = curl_string.strip()
    try:    tokens = shlex.split(curl_string)
    except ValueError as e: raise ValueError(f"Không thể parse curl: {e}")
    if not tokens or tokens[0].lower() != 'curl':
        raise ValueError("Chuỗi phải bắt đầu bằng 'curl'")

    r = {"method": None, "url": None, "headers": {}, "body": None,
         "auth": None, "verify_ssl": True, "allow_redirects": True, "timeout": 30}
    i = 1
    while i < len(tokens):
        t = tokens[i]
        if not t.startswith('-') and r["url"] is None:
            r["url"] = t; i += 1; continue
        if t in ('-X', '--request'):
            i += 1; r["method"] = tokens[i].upper()
        elif t in ('-H', '--header'):
            i += 1
            if ':' in tokens[i]:
                k, _, v = tokens[i].partition(':')
                r["headers"][k.strip()] = v.strip()
        elif t in ('-d', '--data', '--data-raw', '--data-ascii', '--data-binary'):
            i += 1
            raw = tokens[i]
            r["body"] = open(raw[1:], 'rb').read() if raw.startswith('@') else raw
        elif t in ('-F', '--form'):
            i += 1
            if r["body"] is None: r["body"] = {}
            k, _, v = tokens[i].partition('=')
            if isinstance(r["body"], dict): r["body"][k] = v
        elif t in ('-A', '--user-agent'):
            i += 1; r["headers"]["User-Agent"] = tokens[i]
        elif t in ('-u', '--user'):
            i += 1; r["auth"] = tuple(tokens[i].split(':', 1))
        elif t in ('-k', '--insecure'):   r["verify_ssl"] = False
        elif t in ('-L', '--location'):   r["allow_redirects"] = True
        elif t == '--url':
            i += 1; r["url"] = tokens[i]
        elif t in ('--max-time', '-m'):
            i += 1
            try: r["timeout"] = float(tokens[i])
            except: pass
        elif t == '--oauth2-bearer':
            i += 1; r["headers"]["Authorization"] = f"Bearer {tokens[i]}"
        i += 1

    if r["url"] is None:    raise ValueError("Không tìm thấy URL trong chuỗi curl")
    if r["method"] is None: r["method"] = "POST" if r["body"] else "GET"
    return r

def execute_request(parsed: dict):
    kwargs = {
        "headers": parsed["headers"], "auth": parsed["auth"],
        "verify":  parsed["verify_ssl"], "allow_redirects": parsed["allow_redirects"],
        "timeout": parsed["timeout"],
    }
    body = parsed["body"]
    if isinstance(body, dict):
        kwargs["files"] = body
    elif isinstance(body, str):
        ct = parsed["headers"].get("Content-Type", parsed["headers"].get("content-type", ""))
        if "application/json" in ct:
            try:    kwargs["json"] = json.loads(body)
            except: kwargs["data"] = body
        else:
            kwargs["data"] = body
    elif isinstance(body, bytes):
        kwargs["data"] = body
    t0 = time.time()
    resp = requests.request(parsed["method"], parsed["url"], **kwargs)
    return resp, (time.time() - t0) * 1000

def beautify_curl_body(curl_str: str) -> str:
    """
    Tìm -d / --data-raw trong curl string, format JSON body nếu có.
    Trả về curl string đã được format.
    """
    pattern = re.compile(
        r"(-d|--data|--data-raw|--data-binary|--data-ascii)\s+"
        r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")",
        re.DOTALL
    )
    def _fmt(m):
        flag  = m.group(1)
        raw   = m.group(2)
        quote = raw[0]
        inner = raw[1:-1]
        # unescape inner quotes
        inner_unesc = inner.replace(f"\\{quote}", quote)
        try:
            obj    = json.loads(inner_unesc)
            pretty = json.dumps(obj, indent=2, ensure_ascii=False)
            # re-escape for the original quote style
            pretty_esc = pretty.replace(quote, f"\\{quote}")
            return f"{flag} {quote}{pretty_esc}{quote}"
        except Exception:
            return m.group(0)
    return pattern.sub(_fmt, curl_str)

# ══════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════
BG       = "#1a1d23"
BG2      = "#22262f"
BG3      = "#2a2f3a"
SIDEBAR  = "#181b20"
BORDER   = "#353b4a"
ACCENT   = "#e8642a"
ACCENT2  = "#f0883e"
TEXT     = "#e8eaf0"
TEXT_DIM = "#7a8099"
TEXT_URL = "#a8d8f0"
GREEN    = "#4caf7d"
RED_C    = "#f06060"
YELLOW_C = "#f0c060"
CYAN_C   = "#60c8f0"
MAG_C    = "#c060f0"
TAB_BG   = "#20242c"

METHOD_COLORS = {
    "GET": "#4caf7d", "POST": "#e8642a", "PUT": "#f0c060",
    "PATCH": "#c060f0", "DELETE": "#f06060",
    "HEAD": "#60c8f0", "OPTIONS": "#7a8099",
}

def status_color(code):
    if 200 <= code < 300: return GREEN
    if 300 <= code < 400: return YELLOW_C
    if 400 <= code < 500: return RED_C
    return MAG_C

# ══════════════════════════════════════════════
# TAB DATA MODEL
# ══════════════════════════════════════════════
class RequestTab:
    """Lưu toàn bộ state của 1 tab request."""
    _counter = 0

    def __init__(self, name=None, curl="", pre_script=""):
        RequestTab._counter += 1
        self.id         = str(uuid.uuid4())[:8]
        self.name       = name or f"Tab {RequestTab._counter}"
        self.curl       = curl
        self.pre_script = pre_script
        # Response state
        self.response       = None
        self.parsed         = None
        self.elapsed        = None
        self.body_text      = ""
        self.detected_enc   = ""
        self.pre_logs       = []

# ══════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════
class CurlRunnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Curl Runner v3")
        self.geometry("1380x860")
        self.minsize(960, 640)
        self.configure(bg=BG)

        self.history      = _load(HIST_FILE, [])
        self.collections  = _load(COLL_FILE, {})
        self.environments = _load(ENV_FILE,  {"Default": {}})
        self.active_env   = list(self.environments.keys())[0]

        # Multi-tab state
        self.tabs: list[RequestTab] = []
        self.active_tab_idx = -1

        self._setup_fonts()
        self._build_ui()
        self._new_tab()   # Start with 1 blank tab
        self._refresh_history_list()
        self._refresh_collection_tree()
        self._refresh_env_selector()

    # ── FONTS ─────────────────────────────────
    def _setup_fonts(self):
        self.fn_mono  = tkfont.Font(family="Consolas", size=10)
        self.fn_monos = tkfont.Font(family="Consolas", size=9)
        self.fn_title = tkfont.Font(family="Segoe UI", size=13, weight="bold")
        self.fn_label = tkfont.Font(family="Segoe UI", size=9)
        self.fn_btn   = tkfont.Font(family="Segoe UI", size=9,  weight="bold")
        self.fn_stat  = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.fn_badge = tkfont.Font(family="Segoe UI", size=8,  weight="bold")
        self.fn_small = tkfont.Font(family="Segoe UI", size=8)
        self.fn_tab   = tkfont.Font(family="Segoe UI", size=9)

    # ── TOP BAR ───────────────────────────────
    def _build_ui(self):
        topbar = tk.Frame(self, bg=BG2, height=48)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        tk.Label(topbar, text="⚡ CURL RUNNER", font=self.fn_title,
                 bg=BG2, fg=ACCENT).pack(side="left", padx=16, pady=8)
        tk.Label(topbar, text="v3  ·  Multi-tab · Pre-script · Beautify",
                 font=self.fn_label, bg=BG2, fg=TEXT_DIM).pack(side="left")

        ef = tk.Frame(topbar, bg=BG2)
        ef.pack(side="right", padx=16)
        tk.Label(ef, text="ENV:", font=self.fn_badge, bg=BG2, fg=TEXT_DIM).pack(side="left")
        self.env_var = tk.StringVar(value=self.active_env)
        self.env_combo = ttk.Combobox(ef, textvariable=self.env_var, width=16,
                                      state="readonly", font=self.fn_label)
        self.env_combo.pack(side="left", padx=4)
        self.env_combo.bind("<<ComboboxSelected>>", self._on_env_change)
        self._mkbtn(ef, "⚙ Manage", self._open_env_editor, side="left", pad=(4,0))

        # 3-column layout
        outer = tk.PanedWindow(self, orient="horizontal", bg=BG,
                               sashwidth=4, sashrelief="flat", bd=0)
        outer.pack(fill="both", expand=True)
        outer.add(self._build_sidebar(outer), minsize=200, width=240)
        outer.add(self._build_center(outer),  minsize=380, width=560)
        outer.add(self._build_right(outer),   minsize=300)

    # ══ SIDEBAR ═══════════════════════════════
    def _build_sidebar(self, parent):
        frame = tk.Frame(parent, bg=SIDEBAR)
        tab_row = tk.Frame(frame, bg=SIDEBAR)
        tab_row.pack(fill="x")
        for lbl, val in [("📋 History","history"),("🗂 Collections","collections")]:
            btn = tk.Button(tab_row, text=lbl, font=self.fn_small,
                            bg=BG3 if val=="history" else SIDEBAR,
                            fg=ACCENT if val=="history" else TEXT_DIM,
                            relief="flat", cursor="hand2", pady=6, bd=0,
                            command=lambda v=val: self._show_sidebar(v))
            btn.pack(side="left", fill="x", expand=True)
            setattr(self, f"stab_{val}", btn)
        self.sidebar_history     = tk.Frame(frame, bg=SIDEBAR)
        self.sidebar_collections = tk.Frame(frame, bg=SIDEBAR)
        self._build_history_panel(self.sidebar_history)
        self._build_collection_panel(self.sidebar_collections)
        self.sidebar_history.pack(fill="both", expand=True)
        return frame

    def _show_sidebar(self, val):
        for v, fr in [("history",self.sidebar_history),
                      ("collections",self.sidebar_collections)]:
            getattr(self, f"stab_{v}").config(
                bg=BG3 if v==val else SIDEBAR,
                fg=ACCENT if v==val else TEXT_DIM)
            if v == val: fr.pack(fill="both", expand=True)
            else:        fr.pack_forget()

    # ── History ──
    def _build_history_panel(self, parent):
        sf = tk.Frame(parent, bg=SIDEBAR)
        sf.pack(fill="x", padx=6, pady=(6,2))
        self.hist_search = tk.Entry(sf, bg=BG3, fg=TEXT_DIM,
                                    insertbackground=ACCENT,
                                    font=self.fn_small, relief="flat", bd=0)
        self.hist_search.pack(fill="x", ipady=4, padx=1)
        self.hist_search.insert(0, "🔍 Tìm kiếm...")
        self.hist_search.bind("<FocusIn>",    lambda e: self._hist_focus(True))
        self.hist_search.bind("<FocusOut>",   lambda e: self._hist_focus(False))
        self.hist_search.bind("<KeyRelease>", lambda e: self._refresh_history_list())

        lf = tk.Frame(parent, bg=SIDEBAR)
        lf.pack(fill="both", expand=True, padx=6, pady=2)
        sb = tk.Scrollbar(lf, bg=BG3, troughcolor=SIDEBAR, bd=0)
        sb.pack(side="right", fill="y")
        self.hist_list = tk.Listbox(lf, bg=BG2, fg=TEXT, font=self.fn_small,
                                    selectbackground=ACCENT, selectforeground="#fff",
                                    relief="flat", bd=0, activestyle="none",
                                    yscrollcommand=sb.set)
        self.hist_list.pack(fill="both", expand=True)
        sb.config(command=self.hist_list.yview)
        self.hist_list.bind("<Double-Button-1>", self._load_from_history)
        self.hist_list.bind("<Button-3>",        self._history_ctx)

        bf = tk.Frame(parent, bg=SIDEBAR)
        bf.pack(fill="x", padx=6, pady=(2,6))
        self._mkbtn(bf, "Xóa hết", self._clear_history)

    def _hist_focus(self, on):
        ph = "🔍 Tìm kiếm..."
        if on and self.hist_search.get() == ph:
            self.hist_search.delete(0,"end"); self.hist_search.config(fg=TEXT)
        elif not on and not self.hist_search.get():
            self.hist_search.insert(0, ph); self.hist_search.config(fg=TEXT_DIM)

    def _refresh_history_list(self, *_):
        q = self.hist_search.get().lower()
        if q == "🔍 tìm kiếm...": q = ""
        self.hist_list.delete(0,"end")
        for item in reversed(self.history[-300:]):
            method = item.get("method","?")
            url    = item.get("url","")
            sc     = str(item.get("status",""))
            if q and q not in f"{method} {url}".lower() and q not in sc: continue
            self.hist_list.insert("end", f"  {method:5} {url[:30]}")
            col = status_color(int(sc)) if sc.isdigit() else TEXT_DIM
            self.hist_list.itemconfig(self.hist_list.size()-1, fg=col)

    def _get_visible_history(self):
        q = self.hist_search.get().lower()
        if q == "🔍 tìm kiếm...": q = ""
        out = []
        for item in reversed(self.history[-300:]):
            method = item.get("method","?"); url = item.get("url","")
            sc     = str(item.get("status",""))
            if q and q not in f"{method} {url}".lower() and q not in sc: continue
            out.append(item)
        return out

    def _load_from_history(self, _=None):
        sel = self.hist_list.curselection()
        if not sel: return
        visible = self._get_visible_history()
        if sel[0] < len(visible):
            self._set_curl(visible[sel[0]].get("curl",""))

    def _history_ctx(self, event):
        idx = self.hist_list.nearest(event.y)
        self.hist_list.selection_clear(0,"end")
        self.hist_list.selection_set(idx)
        visible = self._get_visible_history()
        m = tk.Menu(self, tearoff=0, bg=BG3, fg=TEXT, activebackground=ACCENT)
        m.add_command(label="▶  Load vào tab hiện tại", command=self._load_from_history)
        m.add_command(label="➕ Mở trong tab mới",
                      command=lambda: self._load_history_new_tab(idx, visible))
        m.add_command(label="📁 Lưu vào Collection",
                      command=lambda: self._save_to_coll_dialog(
                          visible[idx].get("curl","") if idx < len(visible) else ""))
        m.add_separator()
        m.add_command(label="🗑 Xóa",
                      command=lambda: self._del_hist_item(idx, visible))
        m.tk_popup(event.x_root, event.y_root)

    def _load_history_new_tab(self, idx, visible):
        if idx < len(visible):
            curl = visible[idx].get("curl","")
            self._new_tab(curl=curl)

    def _del_hist_item(self, idx, visible):
        if idx >= len(visible): return
        tid = visible[idx].get("id")
        self.history = [h for h in self.history if h.get("id") != tid]
        _save(HIST_FILE, self.history)
        self._refresh_history_list()

    def _clear_history(self):
        if messagebox.askyesno("Xác nhận","Xóa toàn bộ lịch sử?"):
            self.history = []
            _save(HIST_FILE, self.history)
            self._refresh_history_list()

    # ── Collections ──
    def _build_collection_panel(self, parent):
        bf = tk.Frame(parent, bg=SIDEBAR)
        bf.pack(fill="x", padx=6, pady=(6,2))
        self._mkbtn(bf, "＋ New Collection", self._new_collection)

        tf = tk.Frame(parent, bg=SIDEBAR)
        tf.pack(fill="both", expand=True, padx=6, pady=2)
        sb = tk.Scrollbar(tf, bg=BG3, troughcolor=SIDEBAR, bd=0)
        sb.pack(side="right", fill="y")
        self.coll_tree = ttk.Treeview(tf, show="tree", selectmode="browse",
                                      yscrollcommand=sb.set)
        sb.config(command=self.coll_tree.yview)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=BG2, foreground=TEXT,
                        fieldbackground=BG2, font=("Segoe UI",9),
                        rowheight=24, borderwidth=0)
        style.map("Treeview", background=[("selected",ACCENT)],
                  foreground=[("selected","#fff")])
        self.coll_tree.pack(fill="both", expand=True)
        self.coll_tree.bind("<Double-Button-1>", self._load_from_collection)
        self.coll_tree.bind("<Button-3>",        self._coll_ctx)

    def _refresh_collection_tree(self):
        self.coll_tree.delete(*self.coll_tree.get_children())
        for col_name, items in self.collections.items():
            node = self.coll_tree.insert("","end",
                                         text=f"📁 {col_name} ({len(items)})",
                                         open=True, tags=("col",))
            for it in items:
                self.coll_tree.insert(node,"end",
                                      text=f"  {it.get('method','GET'):5} {it.get('name','')}",
                                      values=(col_name, it["id"]), tags=("item",))
        self.coll_tree.tag_configure("col",  foreground=YELLOW_C)
        self.coll_tree.tag_configure("item", foreground=TEXT)

    def _load_from_collection(self, _=None):
        sel = self.coll_tree.selection()
        if not sel: return
        vals = self.coll_tree.item(sel[0],"values")
        if not vals or len(vals) < 2: return
        col_name, item_id = vals[0], vals[1]
        for it in self.collections.get(col_name,[]):
            if it["id"] == item_id:
                self._set_curl(it["curl"]); return

    def _coll_ctx(self, event):
        iid = self.coll_tree.identify_row(event.y)
        if not iid: return
        self.coll_tree.selection_set(iid)
        vals = self.coll_tree.item(iid,"values")
        m = tk.Menu(self, tearoff=0, bg=BG3, fg=TEXT, activebackground=ACCENT)
        if vals and len(vals) >= 2:
            col_name, item_id = vals[0], vals[1]
            m.add_command(label="▶  Load vào tab hiện tại",
                          command=self._load_from_collection)
            m.add_command(label="➕ Mở trong tab mới",
                          command=lambda: self._open_coll_item_new_tab(col_name, item_id))
            m.add_separator()
            m.add_command(label="✏  Đổi tên",
                          command=lambda: self._rename_coll_item(col_name, item_id))
            m.add_command(label="🗑 Xóa",
                          command=lambda: self._del_coll_item(col_name, item_id))
        else:
            col_name = self.coll_tree.item(iid,"text").split(" (")[0].replace("📁 ","")
            m.add_command(label="🗑 Xóa Collection",
                          command=lambda: self._del_collection(col_name))
        m.tk_popup(event.x_root, event.y_root)

    def _open_coll_item_new_tab(self, col_name, item_id):
        for it in self.collections.get(col_name,[]):
            if it["id"] == item_id:
                self._new_tab(curl=it["curl"], name=it.get("name"))
                return

    def _new_collection(self):
        name = simpledialog.askstring("Tên Collection","Nhập tên mới:", parent=self)
        if name and name.strip():
            self.collections.setdefault(name.strip(),[])
            _save(COLL_FILE, self.collections)
            self._refresh_collection_tree()

    def _save_to_coll_dialog(self, curl_str):
        if not curl_str: return
        if not self.collections:
            if messagebox.askyesno("Chưa có Collection","Tạo mới?"):
                self._new_collection()
            if not self.collections: return
        win = tk.Toplevel(self)
        win.title("Lưu vào Collection")
        win.configure(bg=BG); win.geometry("360x210"); win.grab_set()
        tk.Label(win, text="Collection:", font=self.fn_label,
                 bg=BG, fg=TEXT_DIM).pack(pady=(16,2))
        col_var = tk.StringVar(value=list(self.collections.keys())[0])
        ttk.Combobox(win, textvariable=col_var,
                     values=list(self.collections.keys()),
                     state="readonly", font=self.fn_label).pack(padx=20, fill="x")
        tk.Label(win, text="Tên request:", font=self.fn_label,
                 bg=BG, fg=TEXT_DIM).pack(pady=(10,2))
        name_e = tk.Entry(win, font=self.fn_label, bg=BG3, fg=TEXT,
                          insertbackground=ACCENT, relief="flat")
        name_e.pack(padx=20, fill="x"); name_e.insert(0,"New Request")
        def do_save():
            col  = col_var.get()
            name = name_e.get().strip() or "New Request"
            try:    method = parse_curl(curl_str).get("method","GET")
            except: method = "GET"
            self.collections[col].append({
                "id": str(uuid.uuid4())[:8], "name": name,
                "method": method, "curl": curl_str
            })
            _save(COLL_FILE, self.collections)
            self._refresh_collection_tree()
            win.destroy()
        tk.Button(win, text="💾 Lưu", font=self.fn_btn, bg=ACCENT, fg="#fff",
                  relief="flat", command=do_save, pady=6).pack(pady=14)

    def _rename_coll_item(self, col_name, item_id):
        for it in self.collections.get(col_name,[]):
            if it["id"] == item_id:
                new = simpledialog.askstring("Đổi tên","Tên mới:",
                                             initialvalue=it["name"], parent=self)
                if new:
                    it["name"] = new.strip()
                    _save(COLL_FILE, self.collections)
                    self._refresh_collection_tree()
                return

    def _del_coll_item(self, col_name, item_id):
        self.collections[col_name] = [i for i in self.collections.get(col_name,[])
                                       if i["id"] != item_id]
        _save(COLL_FILE, self.collections); self._refresh_collection_tree()

    def _del_collection(self, col_name):
        if messagebox.askyesno("Xác nhận", f"Xóa '{col_name}'?"):
            self.collections.pop(col_name, None)
            _save(COLL_FILE, self.collections); self._refresh_collection_tree()

    # ══ ENVIRONMENT ═══════════════════════════
    def _refresh_env_selector(self):
        names = list(self.environments.keys())
        self.env_combo["values"] = names
        if self.active_env not in names:
            self.active_env = names[0] if names else "Default"
        self.env_var.set(self.active_env)

    def _on_env_change(self, _=None):
        self.active_env = self.env_var.get()
        self._update_env_hint()

    def _open_env_editor(self):
        win = tk.Toplevel(self)
        win.title("Environment Manager")
        win.configure(bg=BG); win.geometry("640x480"); win.grab_set()

        top = tk.Frame(win, bg=BG)
        top.pack(fill="x", padx=12, pady=(10,4))
        tk.Label(top, text="Environment:", font=self.fn_label,
                 bg=BG, fg=TEXT_DIM).pack(side="left")
        env_sel = tk.StringVar(value=self.active_env)
        env_cb  = ttk.Combobox(top, textvariable=env_sel,
                                values=list(self.environments.keys()),
                                state="readonly", font=self.fn_label, width=18)
        env_cb.pack(side="left", padx=6)

        def new_env():
            n = simpledialog.askstring("Tên","Tên environment mới:", parent=win)
            if n and n.strip():
                self.environments.setdefault(n.strip(),{})
                env_cb["values"] = list(self.environments.keys())
                env_sel.set(n.strip()); load_vars()

        def del_env():
            n = env_sel.get()
            if len(self.environments) <= 1:
                messagebox.showinfo("","Phải giữ ít nhất 1."); return
            if messagebox.askyesno("Xác nhận", f"Xóa '{n}'?", parent=win):
                self.environments.pop(n, None)
                env_cb["values"] = list(self.environments.keys())
                env_sel.set(list(self.environments.keys())[0]); load_vars()

        self._mkbtn(top, "＋ Mới", new_env, side="left", pad=(4,0))
        self._mkbtn(top, "🗑",     del_env, side="left", pad=(4,0))

        tbl = tk.Frame(win, bg=BG2)
        tbl.pack(fill="both", expand=True, padx=12, pady=4)
        cols = ("variable","value")
        tree = ttk.Treeview(tbl, columns=cols, show="headings", height=14)
        tree.heading("variable", text="Variable  ({{tên}})")
        tree.heading("value",    text="Value")
        tree.column("variable", width=200); tree.column("value", width=380)
        vsb = tk.Scrollbar(tbl, command=tree.yview, bg=BG3, troughcolor=BG2, bd=0)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); tree.pack(fill="both", expand=True)

        def load_vars():
            tree.delete(*tree.get_children())
            for k, v in self.environments.get(env_sel.get(),{}).items():
                tree.insert("","end", values=(k,v))

        env_cb.bind("<<ComboboxSelected>>", lambda e: load_vars())
        load_vars()

        def edit_cell(event):
            iid = tree.identify_row(event.y)
            col = tree.identify_column(event.x)
            if not iid: return
            x,y,w,h = tree.bbox(iid,col)
            col_idx  = int(col[1:])-1
            val      = tree.item(iid,"values")[col_idx]
            ent = tk.Entry(tbl, font=self.fn_label, bg=BG3, fg=TEXT,
                           insertbackground=ACCENT, relief="flat", bd=1)
            ent.place(x=x,y=y,width=w,height=h)
            ent.insert(0,val); ent.focus_set()
            def commit(_=None):
                vals = list(tree.item(iid,"values"))
                vals[col_idx] = ent.get()
                tree.item(iid, values=vals); ent.destroy()
            ent.bind("<Return>",   commit)
            ent.bind("<FocusOut>", commit)

        tree.bind("<Double-Button-1>", edit_cell)

        bf = tk.Frame(win, bg=BG)
        bf.pack(fill="x", padx=12, pady=(4,12))

        def save_close():
            env_name = env_sel.get()
            self.environments[env_name] = {}
            for iid in tree.get_children():
                k,v = tree.item(iid,"values")
                if k.strip(): self.environments[env_name][k.strip()] = v
            _save(ENV_FILE, self.environments)
            self._refresh_env_selector()
            self.active_env = env_name
            self.env_var.set(env_name)
            self._update_env_hint()
            win.destroy()

        self._mkbtn(bf, "＋ Thêm dòng",
                    lambda: tree.insert("","end",values=("NEW_VAR","value")), side="left")
        self._mkbtn(bf, "🗑 Xóa dòng",
                    lambda: tree.delete(tree.selection()[0]) if tree.selection() else None,
                    side="left", pad=(6,0))
        tk.Button(bf, text="💾 Lưu & Đóng", font=self.fn_btn, bg=ACCENT, fg="#fff",
                  relief="flat", command=save_close, pady=5, padx=14).pack(side="right")

    # ══ CENTER (MULTI-TAB INPUT) ══════════════
    def _build_center(self, parent):
        frame = tk.Frame(parent, bg=BG)

        # ── Tab bar
        tab_bar_wrap = tk.Frame(frame, bg=TAB_BG)
        tab_bar_wrap.pack(fill="x", side="top")

        # Scrollable tab bar
        self.tab_canvas = tk.Canvas(tab_bar_wrap, bg=TAB_BG, height=34,
                                    highlightthickness=0, bd=0)
        self.tab_canvas.pack(side="left", fill="x", expand=True)
        self.tab_frame  = tk.Frame(self.tab_canvas, bg=TAB_BG)
        self.tab_canvas.create_window((0,0), window=self.tab_frame, anchor="nw")
        self.tab_frame.bind("<Configure>",
                            lambda e: self.tab_canvas.configure(
                                scrollregion=self.tab_canvas.bbox("all")))

        # New tab button
        tk.Button(tab_bar_wrap, text="＋", font=self.fn_title,
                  bg=TAB_BG, fg=TEXT_DIM, activebackground=BG3,
                  relief="flat", cursor="hand2", padx=10, bd=0,
                  command=self._new_tab).pack(side="right", padx=4)

        # ── Tab content area (swappable)
        self.center_content = tk.Frame(frame, bg=BG)
        self.center_content.pack(fill="both", expand=True)

        return frame

    def _build_tab_content(self, tab: RequestTab) -> tk.Frame:
        """Tạo widget content cho 1 tab."""
        frame = tk.Frame(self.center_content, bg=BG, padx=12, pady=8)

        # Header row
        hdr = tk.Frame(frame, bg=BG)
        hdr.pack(fill="x", pady=(0,4))
        self._sec(hdr, "CURL COMMAND", side="left")
        lbl_env = tk.Label(hdr, text="", font=self.fn_small, bg=BG, fg=TEXT_DIM)
        lbl_env.pack(side="right")
        tab._env_hint_lbl = lbl_env

        # Toolbar
        tb = tk.Frame(frame, bg=BG)
        tb.pack(fill="x", pady=(0,4))
        self._mkbtn(tb, "📂 Import",      lambda t=tab: self._import_file(t),           side="left")
        self._mkbtn(tb, "✨ Beautify",    lambda t=tab: self._beautify_body(t),          side="left", pad=(6,0))
        self._mkbtn(tb, "✂ Xóa",         lambda t=tab: self._clear_input(t),            side="left", pad=(6,0))
        self._mkbtn(tb, "➕ Collection",  lambda t=tab: self._save_tab_to_coll(t),       side="left", pad=(6,0))

        # Notebook: Curl input | Pre-request Script
        nb = ttk.Notebook(frame)
        nb.pack(fill="both", expand=True)

        # ── Curl tab
        curl_frame = tk.Frame(nb, bg=BG2)
        nb.add(curl_frame, text="  curl  ")

        wrap = tk.Frame(curl_frame, bg=BORDER)
        wrap.pack(fill="both", expand=True, padx=1, pady=1)
        curl_tw = tk.Text(wrap, bg=BG2, fg=TEXT, insertbackground=ACCENT,
                          font=self.fn_mono, wrap="word", relief="flat",
                          padx=10, pady=8, selectbackground=ACCENT,
                          selectforeground="#fff", undo=True, bd=0)
        sb_c = tk.Scrollbar(wrap, command=curl_tw.yview, bg=BG3, troughcolor=BG2, bd=0)
        curl_tw.configure(yscrollcommand=sb_c.set)
        sb_c.pack(side="right", fill="y")
        curl_tw.pack(fill="both", expand=True)
        tab._curl_tw = curl_tw

        # Placeholder
        if tab.curl:
            curl_tw.insert("1.0", tab.curl)
        else:
            self._set_ph(curl_tw, tab)
        curl_tw.bind("<FocusIn>",    lambda e, t=tab: self._clear_ph(t))
        curl_tw.bind("<FocusOut>",   lambda e, t=tab: self._restore_ph(t))
        curl_tw.bind("<KeyRelease>", lambda e, t=tab: self._update_env_hint(t))

        # ── Pre-request script tab
        pre_frame = tk.Frame(nb, bg=BG2)
        nb.add(pre_frame, text="  ⚡ Pre-request Script  ")

        pre_hdr = tk.Frame(pre_frame, bg=BG2)
        pre_hdr.pack(fill="x", padx=8, pady=(6,2))
        tk.Label(pre_hdr,
                 text="Python script chạy TRƯỚC khi gửi request. Dùng set_env('key','val') để set biến.",
                 font=self.fn_small, bg=BG2, fg=TEXT_DIM).pack(side="left")
        self._mkbtn(pre_hdr, "📋 Ví dụ",
                    lambda t=tab: self._insert_script_example(t),
                    side="right")

        pre_wrap = tk.Frame(pre_frame, bg=BORDER)
        pre_wrap.pack(fill="both", expand=True, padx=8, pady=(2,4))
        pre_tw = tk.Text(pre_wrap, bg="#1e2430", fg=TEXT, insertbackground=ACCENT,
                         font=self.fn_mono, wrap="none", relief="flat",
                         padx=10, pady=8, selectbackground=ACCENT,
                         selectforeground="#fff", undo=True, bd=0,
                         tabs=("28",))
        sb_p = tk.Scrollbar(pre_wrap, command=pre_tw.yview, bg=BG3, troughcolor=BG2, bd=0)
        pre_tw.configure(yscrollcommand=sb_p.set)
        sb_p.pack(side="right", fill="y")
        pre_tw.pack(fill="both", expand=True)
        tab._pre_tw = pre_tw

        if tab.pre_script:
            pre_tw.insert("1.0", tab.pre_script)
        else:
            pre_tw.insert("1.0", "# Viết Python script ở đây\n# Ví dụ: set_env('token', 'abc123')\n")
            pre_tw.config(fg=TEXT_DIM)
        pre_tw.bind("<FocusIn>", lambda e, tw=pre_tw: (
            tw.config(fg=TEXT) if tw.get("1.0","end").strip().startswith("#") else None
        ))

        # Style notebook tabs
        style = ttk.Style()
        style.configure("TNotebook", background=BG2, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground=TEXT_DIM,
                        padding=[10,4], font=("Segoe UI",9))
        style.map("TNotebook.Tab",
                  background=[("selected",BG2)],
                  foreground=[("selected",ACCENT)])

        tab._nb = nb

        # ── Options
        opt = tk.Frame(frame, bg=BG)
        opt.pack(fill="x", pady=(6,2))
        tab._var_ssl      = tk.BooleanVar(value=True)
        tab._var_redirect = tk.BooleanVar(value=True)
        tab._var_decode   = tk.BooleanVar(value=True)
        self._chk(opt, "Verify SSL",      tab._var_ssl)
        self._chk(opt, "Follow Redirect", tab._var_redirect)
        self._chk(opt, "Auto Decode",     tab._var_decode)
        tk.Label(opt, text="Timeout (s):", font=self.fn_label,
                 bg=BG, fg=TEXT_DIM).pack(side="left", padx=(10,4))
        tab._timeout_var = tk.StringVar(value="30")
        tk.Entry(opt, textvariable=tab._timeout_var, font=self.fn_monos,
                 bg=BG3, fg=TEXT, insertbackground=ACCENT,
                 relief="flat", width=5, bd=0).pack(side="left")

        # ── Send button
        send_btn = tk.Button(
            frame, text="▶  SEND REQUEST",
            font=self.fn_btn, bg=ACCENT, fg="white",
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", cursor="hand2", padx=20, pady=8,
            command=lambda t=tab: self._send(t)
        )
        send_btn.pack(fill="x", pady=(8,2))
        tab._send_btn = send_btn

        status_lbl = tk.Label(frame, text="", font=self.fn_label,
                              bg=BG, fg=TEXT_DIM, anchor="w")
        status_lbl.pack(fill="x")
        tab._status_lbl = status_lbl

        return frame

    # ── Tab bar management ────────────────────
    def _new_tab(self, curl="", name=None, pre_script=""):
        tab = RequestTab(name=name, curl=curl, pre_script=pre_script)
        self.tabs.append(tab)
        self._render_tab_bar()
        self._switch_tab(len(self.tabs)-1)

    def _render_tab_bar(self):
        for w in self.tab_frame.winfo_children():
            w.destroy()
        for i, tab in enumerate(self.tabs):
            is_active = (i == self.active_tab_idx)
            frm = tk.Frame(self.tab_frame,
                           bg=BG if is_active else TAB_BG,
                           padx=2, pady=0)
            frm.pack(side="left", padx=(0,1))

            # Editable tab name on double-click
            lbl = tk.Label(frm,
                           text=f"  {tab.name[:14]}  ",
                           font=self.fn_tab,
                           bg=BG if is_active else TAB_BG,
                           fg=ACCENT if is_active else TEXT_DIM,
                           cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>",        lambda e, idx=i: self._switch_tab(idx))
            lbl.bind("<Double-Button-1>", lambda e, idx=i: self._rename_tab(idx))

            # Close button (hide if only 1 tab)
            if len(self.tabs) > 1:
                close = tk.Label(frm, text="✕", font=self.fn_small,
                                 bg=BG if is_active else TAB_BG,
                                 fg=TEXT_DIM, cursor="hand2", padx=2)
                close.pack(side="left")
                close.bind("<Button-1>", lambda e, idx=i: self._close_tab(idx))

            # Bottom border for active tab
            if is_active:
                indicator = tk.Frame(frm, bg=ACCENT, height=2)
                indicator.pack(fill="x", side="bottom")

    def _switch_tab(self, idx):
        # Save current tab's content before switching
        if self.active_tab_idx >= 0 and self.active_tab_idx < len(self.tabs):
            self._save_tab_state(self.tabs[self.active_tab_idx])

        # Hide all content frames
        for w in self.center_content.winfo_children():
            w.pack_forget()

        self.active_tab_idx = idx
        tab = self.tabs[idx]

        # Build content frame if not yet built
        if not hasattr(tab, "_frame") or tab._frame is None:
            tab._frame = self._build_tab_content(tab)

        tab._frame.pack(fill="both", expand=True)
        self._render_tab_bar()
        self._update_env_hint(tab)

        # Restore response panel
        if tab.response is not None:
            self._restore_response(tab)
        else:
            self._clear_response_panel()

    def _save_tab_state(self, tab):
        if not hasattr(tab, "_curl_tw"): return
        curl = tab._curl_tw.get("1.0","end").strip()
        tab.curl = "" if getattr(tab,"_ph_active",False) else curl
        if hasattr(tab, "_pre_tw"):
            tab.pre_script = tab._pre_tw.get("1.0","end").strip()

    def _close_tab(self, idx):
        if len(self.tabs) <= 1: return
        self._save_tab_state(self.tabs[idx])
        # Destroy frame
        if hasattr(self.tabs[idx], "_frame") and self.tabs[idx]._frame:
            self.tabs[idx]._frame.destroy()
        self.tabs.pop(idx)
        new_idx = min(idx, len(self.tabs)-1)
        self.active_tab_idx = -1
        self._switch_tab(new_idx)

    def _rename_tab(self, idx):
        tab = self.tabs[idx]
        new = simpledialog.askstring("Đổi tên tab","Tên mới:",
                                     initialvalue=tab.name, parent=self)
        if new and new.strip():
            tab.name = new.strip()
            self._render_tab_bar()

    # ── Placeholder per-tab ───────────────────
    PH = ("Paste hoặc nhập curl command...\n\n"
          "Hỗ trợ biến: curl {{base_url}}/api \\\n"
          "  -H 'Authorization: Bearer {{token}}'\n\n"
          "Ví dụ: curl https://httpbin.org/get")

    def _set_ph(self, tw, tab):
        tw.insert("1.0", self.PH)
        tw.config(fg="#555b70")
        tab._ph_active = True

    def _clear_ph(self, tab):
        if getattr(tab,"_ph_active",False):
            tab._curl_tw.delete("1.0","end")
            tab._curl_tw.config(fg=TEXT)
            tab._ph_active = False

    def _restore_ph(self, tab):
        if not tab._curl_tw.get("1.0","end").strip():
            self._set_ph(tab._curl_tw, tab)

    def _set_curl(self, curl_str):
        """Load curl vào tab đang active."""
        if self.active_tab_idx < 0: return
        tab = self.tabs[self.active_tab_idx]
        if not hasattr(tab,"_curl_tw"): return
        self._clear_ph(tab)
        tab._curl_tw.delete("1.0","end")
        tab._curl_tw.insert("1.0", curl_str)
        tab.curl = curl_str
        self._update_env_hint(tab)

    def _update_env_hint(self, tab=None):
        if tab is None:
            if self.active_tab_idx < 0: return
            tab = self.tabs[self.active_tab_idx]
        if not hasattr(tab,"_curl_tw"): return
        text  = tab._curl_tw.get("1.0","end")
        found = re.findall(r'\{\{(\w+)\}\}', text)
        lbl   = getattr(tab,"_env_hint_lbl", None)
        if not lbl: return
        if not found:
            lbl.config(text=""); return
        env = self.environments.get(self.active_env,{})
        ok  = [v for v in set(found) if v in env]
        bad = [v for v in set(found) if v not in env]
        parts = []
        if ok:  parts.append(f"✓ {', '.join(ok)}")
        if bad: parts.append(f"✗ {', '.join(bad)}")
        lbl.config(text="  ".join(parts), fg=RED_C if bad else GREEN)

    # ── Beautify ──────────────────────────────
    def _beautify_body(self, tab):
        if not hasattr(tab,"_curl_tw"): return
        self._clear_ph(tab)
        raw = tab._curl_tw.get("1.0","end").strip()
        if not raw: return
        result = beautify_curl_body(raw)
        if result != raw:
            tab._curl_tw.delete("1.0","end")
            tab._curl_tw.insert("1.0", result)
            tab._status_lbl.config(text="✨ Body đã được format", fg=GREEN)
        else:
            tab._status_lbl.config(text="Body không phải JSON hoặc đã format rồi", fg=TEXT_DIM)

    # ── Script example ────────────────────────
    def _insert_script_example(self, tab):
        example = (
            "# ── Ví dụ 1: Set token thủ công ─────────────────\n"
            "set_env('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...')\n\n"
            "# ── Ví dụ 2: Lấy token từ API login ─────────────\n"
            "# resp = requests.post(env.get('base_url','') + '/auth/login',\n"
            "#     json={'username': 'admin', 'password': 'secret'},\n"
            "#     timeout=10)\n"
            "# if resp.ok:\n"
            "#     token = resp.json()['data']['token']\n"
            "#     set_env('token', token)\n"
            "#     log(f'Token: {token[:20]}...')\n"
            "# else:\n"
            "#     log(f'Login thất bại: {resp.status_code}')\n\n"
            "# ── Ví dụ 3: Tính timestamp ───────────────────────\n"
            "# import time\n"
            "# set_env('timestamp', str(int(time.time())))\n"
        )
        if hasattr(tab,"_pre_tw"):
            tab._pre_tw.delete("1.0","end")
            tab._pre_tw.insert("1.0", example)
            tab._pre_tw.config(fg=TEXT)

    # ── Import file ───────────────────────────
    def _import_file(self, tab=None):
        if tab is None:
            if self.active_tab_idx < 0: return
            tab = self.tabs[self.active_tab_idx]
        path = filedialog.askopenfilename(
            title="Chọn file curl",
            filetypes=[("Text/Shell","*.txt *.sh *.curl"),("All","*.*")])
        if not path: return
        try:
            with open(path,"r",encoding="utf-8") as f: content = f.read().strip()
            lines, out, found = content.splitlines(), [], False
            for line in lines:
                s = line.strip()
                if s.lower().startswith("curl "): found = True
                if found:
                    out.append(line)
                    if not s.endswith("\\") and not s.endswith("^"): break
            self._clear_ph(tab)
            tab._curl_tw.delete("1.0","end")
            tab._curl_tw.insert("1.0", "\n".join(out) if out else content)
            tab._status_lbl.config(text=f"📂 Đã import: {Path(path).name}", fg=GREEN)
            self._update_env_hint(tab)
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không đọc được file:\n{e}")

    def _clear_input(self, tab):
        if not hasattr(tab,"_curl_tw"): return
        tab._curl_tw.delete("1.0","end")
        self._restore_ph(tab)
        tab._status_lbl.config(text="")
        if hasattr(tab,"_env_hint_lbl"):
            tab._env_hint_lbl.config(text="")

    def _save_tab_to_coll(self, tab):
        if not hasattr(tab,"_curl_tw"): return
        curl_str = tab._curl_tw.get("1.0","end").strip()
        if not curl_str or getattr(tab,"_ph_active",False):
            messagebox.showwarning("","Hãy nhập curl command trước."); return
        if not self.collections:
            if messagebox.askyesno("Chưa có Collection","Tạo mới?"):
                self._new_collection()
        self._save_to_coll_dialog(curl_str)

    # ── SEND ──────────────────────────────────
    def _send(self, tab):
        if not hasattr(tab,"_curl_tw"): return
        self._save_tab_state(tab)
        curl_str = tab._curl_tw.get("1.0","end").strip()
        if not curl_str or getattr(tab,"_ph_active",False):
            messagebox.showwarning("Thiếu input","Vui lòng nhập curl command."); return

        # Run pre-request script
        env = dict(self.environments.get(self.active_env,{}))
        pre_script = tab._pre_tw.get("1.0","end").strip() if hasattr(tab,"_pre_tw") else ""
        pre_logs = []
        if pre_script and not pre_script.startswith("#"):
            env, pre_logs = run_pre_script(pre_script, env)
            tab.pre_logs = pre_logs

        curl_resolved = apply_env(curl_str, env)

        tab._send_btn.config(state="disabled", text="⏳  Đang gửi...")
        tab._status_lbl.config(text="Đang gửi...", fg=TEXT_DIM)
        self.status_badge.config(text="…", fg=TEXT_DIM)
        self.time_label.config(text=""); self.size_label.config(text="")

        def worker():
            try:
                parsed = parse_curl(curl_resolved)
                parsed["verify_ssl"]      = tab._var_ssl.get()
                parsed["allow_redirects"] = tab._var_redirect.get()
                try:    parsed["timeout"] = float(tab._timeout_var.get())
                except: parsed["timeout"] = 30
                resp, elapsed = execute_request(parsed)
                self.after(0, lambda: self._display(tab, parsed, resp, elapsed, curl_str, pre_logs))
            except Exception as e:
                self.after(0, lambda: self._show_error(tab, str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ══ RIGHT PANEL (RESPONSE) ════════════════
    def _build_right(self, parent):
        frame = tk.Frame(parent, bg=BG, padx=12, pady=10)

        ss = tk.Frame(frame, bg=BG)
        ss.pack(fill="x", pady=(0,6))
        self._sec(ss, "RESPONSE", side="left")
        self.status_badge = tk.Label(ss, text="—", font=self.fn_stat, bg=BG, fg=TEXT_DIM)
        self.status_badge.pack(side="left", padx=(14,4))
        self.time_label = tk.Label(ss, text="", font=self.fn_label, bg=BG, fg=TEXT_DIM)
        self.time_label.pack(side="left", padx=6)
        self.size_label = tk.Label(ss, text="", font=self.fn_label, bg=BG, fg=TEXT_DIM)
        self.size_label.pack(side="left", padx=6)
        self._mkbtn(ss, "📋 Copy", self._copy_response, side="right")
        self._mkbtn(ss, "💾 Lưu", self._save_response,  side="right", pad=(0,6))

        tr = tk.Frame(frame, bg=BG)
        tr.pack(fill="x")
        for lbl, val in [("Body","body"),("Headers","headers"),("Request Info","info"),("Script Log","log")]:
            btn = tk.Button(tr, text=lbl, font=self.fn_label,
                            bg=BG3 if val=="body" else BG,
                            fg=ACCENT if val=="body" else TEXT_DIM,
                            relief="flat", cursor="hand2", padx=12, pady=5,
                            command=lambda v=val: self._show_resp_tab(v), bd=0)
            btn.pack(side="left", padx=(0,2))
            setattr(self, f"rtab_{val}", btn)

        self.resp_content = tk.Frame(frame, bg=BG)
        self.resp_content.pack(fill="both", expand=True, pady=(4,0))
        self._mk_text_tab("body",    self.fn_mono)
        self._mk_text_tab("headers", self.fn_monos)
        self._mk_text_tab("info",    self.fn_monos)
        self._mk_text_tab("log",     self.fn_monos)

        self.body_tw.tag_configure("key",   foreground=CYAN_C)
        self.body_tw.tag_configure("str",   foreground=GREEN)
        self.body_tw.tag_configure("num",   foreground=YELLOW_C)
        self.body_tw.tag_configure("bool",  foreground=MAG_C)
        self.body_tw.tag_configure("plain", foreground=TEXT)
        self.headers_tw.tag_configure("hk", foreground=CYAN_C)
        self.headers_tw.tag_configure("hv", foreground=TEXT)
        self.info_tw.tag_configure("lbl",    foreground=TEXT_DIM)
        self.info_tw.tag_configure("val",    foreground=TEXT)
        self.info_tw.tag_configure("method", foreground=ACCENT)
        self.info_tw.tag_configure("url",    foreground=TEXT_URL)
        self.log_tw.tag_configure("ok",  foreground=GREEN)
        self.log_tw.tag_configure("err", foreground=RED_C)
        self.log_tw.tag_configure("dim", foreground=TEXT_DIM)

        self._show_resp_tab("body")
        return frame

    def _mk_text_tab(self, name, fnt):
        frame = tk.Frame(self.resp_content, bg=BG)
        wrap  = tk.Frame(frame, bg=BORDER)
        wrap.pack(fill="both", expand=True)
        tw = tk.Text(wrap, bg=BG2, fg=TEXT, font=fnt,
                     wrap="word", relief="flat", padx=10, pady=8,
                     selectbackground=ACCENT, state="disabled", bd=0)
        sb = tk.Scrollbar(wrap, command=tw.yview, bg=BG3, troughcolor=BG2, bd=0)
        tw.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); tw.pack(fill="both", expand=True, padx=1, pady=1)
        setattr(self, f"{name}_frame", frame)
        setattr(self, f"{name}_tw",    tw)

    def _show_resp_tab(self, val):
        for v in ("body","headers","info","log"):
            getattr(self, f"{v}_frame").pack_forget()
            getattr(self, f"rtab_{v}").config(
                bg=BG3 if v==val else BG,
                fg=ACCENT if v==val else TEXT_DIM)
        getattr(self, f"{val}_frame").pack(fill="both", expand=True)

    def _clear_response_panel(self):
        self.status_badge.config(text="—", fg=TEXT_DIM)
        self.time_label.config(text=""); self.size_label.config(text="")
        for name in ("body","headers","info","log"):
            w = getattr(self, f"{name}_tw")
            w.config(state="normal"); w.delete("1.0","end"); w.config(state="disabled")

    def _restore_response(self, tab):
        if tab.response is None: return
        resp    = tab.response
        sc      = resp.status_code
        elapsed = tab.elapsed or 0
        size    = len(resp.content)
        self.status_badge.config(text=f"{sc} {resp.reason}", fg=status_color(sc))
        self.time_label.config(text=f"⏱ {elapsed:.0f} ms", fg=YELLOW_C)
        sz = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB"
        self.size_label.config(text=f"📦 {sz}", fg=TEXT_DIM)
        self._write_body(tab.body_text, resp.headers.get("Content-Type",""))
        self._write_headers(resp.headers)
        self._write_info(tab.parsed, resp, elapsed, tab.detected_enc)
        self._write_log(tab.pre_logs)

    # ── Display response ──────────────────────
    def _display(self, tab, parsed, resp, elapsed, original_curl, pre_logs):
        tab.response = resp
        tab.parsed   = parsed
        tab.elapsed  = elapsed
        tab.pre_logs = pre_logs

        sc   = resp.status_code
        size = len(resp.content)
        self.status_badge.config(text=f"{sc} {resp.reason}", fg=status_color(sc))
        self.time_label.config(text=f"⏱ {elapsed:.0f} ms", fg=YELLOW_C)
        sz = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB"
        self.size_label.config(text=f"📦 {sz}", fg=TEXT_DIM)

        # Decode
        ct_header     = resp.headers.get("Content-Type","")
        charset_match = re.search(r'charset=([^\s;]+)', ct_header, re.I)
        if not tab._var_decode.get():
            body_text = resp.content.decode("latin-1")
            enc_info  = "raw (no decode)"
        elif charset_match:
            charset = charset_match.group(1).strip()
            enc_info = f"{charset}  (từ Content-Type header)"
            try:    body_text = resp.content.decode(charset, errors="replace")
            except: body_text = resp.content.decode("utf-8", errors="replace"); enc_info += " → fallback utf-8"
        elif HAS_DETECT and resp.content:
            result  = detect_encoding(resp.content)
            charset = result.best().encoding if hasattr(result,"best") else "utf-8"
            enc_info = f"{charset}  (auto-detected)"
            try:    body_text = resp.content.decode(charset or "utf-8", errors="replace")
            except: body_text = resp.content.decode("utf-8", errors="replace"); enc_info = "utf-8 (fallback)"
        else:
            body_text = resp.content.decode("utf-8", errors="replace")
            enc_info  = "utf-8 (fallback)"

        tab.body_text    = body_text
        tab.detected_enc = enc_info

        self._write_body(body_text, ct_header)
        self._write_headers(resp.headers)
        self._write_info(parsed, resp, elapsed, enc_info)
        self._write_log(pre_logs)

        tab._send_btn.config(state="normal", text="▶  SEND REQUEST")
        url_s = parsed['url'][:52] + ("..." if len(parsed['url'])>52 else "")
        tab._status_lbl.config(text=f"✓  {parsed['method']}  →  {url_s}", fg=GREEN)

        # Auto-show Script Log tab if script ran
        if pre_logs:
            self._show_resp_tab("log")

        # History
        self.history.append({
            "id":      str(uuid.uuid4())[:8],
            "ts":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "method":  parsed["method"], "url": parsed["url"],
            "curl":    original_curl,    "status": sc,
            "elapsed": round(elapsed),
        })
        self.history = self.history[-500:]
        _save(HIST_FILE, self.history)
        self._refresh_history_list()

    # ── Write panels ──────────────────────────
    def _write_body(self, text, ct):
        w = self.body_tw
        w.config(state="normal"); w.delete("1.0","end")
        if "application/json" in ct or text.strip().startswith(("{","[")):
            try:
                pretty = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
                self._insert_json(w, pretty)
            except: w.insert("end", text, "plain")
        else:
            w.insert("end", text, "plain")
        w.config(state="disabled")

    def _insert_json(self, w, text):
        TOKEN_RE = re.compile(
            r'("(?:[^"\\]|\\.)*")'
            r'|(-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)'
            r'|(true|false|null)'
            r'|([{}\[\]:,])'
            r'|(\s+)'
        )
        pos = 0; expect_key = True
        for m in TOKEN_RE.finditer(text):
            if m.start() > pos: w.insert("end", text[pos:m.start()], "plain")
            pos = m.end()
            s,n,kw,p,sp = m.groups()
            if sp: w.insert("end", sp, "plain")
            elif p:
                w.insert("end", p, "plain")
                if p in ('{',','): expect_key = True
                elif p == ':':     expect_key = False
            elif s:
                w.insert("end", s, "key" if expect_key else "str")
                if expect_key: expect_key = False
            elif n:  w.insert("end", n,  "num")
            elif kw: w.insert("end", kw, "bool")
        if pos < len(text): w.insert("end", text[pos:], "plain")

    def _write_headers(self, headers):
        w = self.headers_tw
        w.config(state="normal"); w.delete("1.0","end")
        for k,v in headers.items():
            w.insert("end", k, "hk"); w.insert("end", f": {v}\n", "hv")
        w.config(state="disabled")

    def _write_info(self, parsed, resp, elapsed, enc_info=""):
        w = self.info_tw
        w.config(state="normal"); w.delete("1.0","end")
        def row(lbl, val, tag="val"):
            w.insert("end", f"  {lbl:<22}","lbl")
            w.insert("end", f"{val}\n", tag)
        w.insert("end","  ── Request ─────────────────────────────\n","lbl")
        row("Method",  parsed["method"],  "method")
        row("URL",     parsed["url"],     "url")
        row("Env",     self.active_env)
        if parsed["headers"]:
            w.insert("end","\n  ── Request Headers ──────────────────────\n","lbl")
            for k,v in parsed["headers"].items(): row(f"  {k}", v)
        if parsed["body"] and not isinstance(parsed["body"], bytes):
            w.insert("end","\n  ── Request Body ─────────────────────────\n","lbl")
            w.insert("end", f"  {str(parsed['body'])[:500]}\n","val")
        w.insert("end","\n  ── Response ─────────────────────────────\n","lbl")
        row("Status",   f"{resp.status_code} {resp.reason}")
        row("Time",     f"{elapsed:.0f} ms")
        row("Size",     f"{len(resp.content):,} bytes")
        row("Encoding", enc_info)
        w.config(state="disabled")

    def _write_log(self, logs: list):
        w = self.log_tw
        w.config(state="normal"); w.delete("1.0","end")
        if not logs:
            w.insert("end","  (Script không có output hoặc chưa chạy)","dim")
        else:
            for line in logs:
                tag = "ok" if line.startswith("✅") else ("err" if line.startswith("❌") else "dim")
                w.insert("end", f"  {line}\n", tag)
        w.config(state="disabled")

    def _show_error(self, tab, msg):
        tab._send_btn.config(state="normal", text="▶  SEND REQUEST")
        self.status_badge.config(text="ERROR", fg=RED_C)
        tab._status_lbl.config(text=f"❌ {msg[:80]}", fg=RED_C)
        self._write_body(f"[LỖI]\n{msg}", "text/plain")

    def _copy_response(self):
        try:
            c = self.body_tw.get("1.0","end").strip()
            if c:
                self.clipboard_clear(); self.clipboard_append(c)
                if self.active_tab_idx >= 0:
                    self.tabs[self.active_tab_idx]._status_lbl.config(
                        text="✓ Đã copy response body", fg=GREEN)
        except: pass

    def _save_response(self):
        if self.active_tab_idx < 0: return
        tab = self.tabs[self.active_tab_idx]
        if tab.response is None:
            messagebox.showinfo("","Hãy gửi request trước."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON","*.json"),("Text","*.txt"),("All","*.*")])
        if path:
            with open(path,"wb") as f: f.write(tab.response.content)
            tab._status_lbl.config(text=f"✓ Đã lưu → {Path(path).name}", fg=GREEN)

    # ── Shared helpers ────────────────────────
    def _sec(self, parent, text, side="top"):
        lbl = tk.Label(parent, text=text, font=self.fn_badge, bg=BG, fg=TEXT_DIM)
        if side=="top": lbl.pack(anchor="w", pady=(0,4))
        else:           lbl.pack(side=side, padx=(0,8))

    def _mkbtn(self, parent, text, cmd, side="left", pad=(0,0)):
        b = tk.Button(parent, text=text, font=self.fn_label,
                      bg=BG3, fg=TEXT, activebackground=BORDER,
                      relief="flat", cursor="hand2",
                      padx=10, pady=4, command=cmd, bd=0)
        b.pack(side=side, padx=pad)
        return b

    def _chk(self, parent, text, var):
        tk.Checkbutton(parent, text=text, variable=var,
                       font=self.fn_label, bg=BG, fg=TEXT_DIM,
                       activebackground=BG, selectcolor=BG3,
                       relief="flat", bd=0).pack(side="left", padx=(0,8))

# ══════════════════════════════════════════════
if __name__ == "__main__":
    app = CurlRunnerApp()
    app.mainloop()
#py -m PyInstaller --onefile --noconsole --name "CurlRunner" curl_runner_gui.py