# models.py — Data models
# type: ignore
import uuid


class RequestTab:
    """Lưu toàn bộ state của 1 tab request (curl, options, response...)."""
    _counter = 0

    def __init__(self, name: str | None = None, curl: str = "", pre_script: str = ""):
        RequestTab._counter += 1
        self.id         = str(uuid.uuid4())[:8]
        self.name       = name or f"Tab {RequestTab._counter}"
        self.curl       = curl
        self.pre_script = pre_script

        # Response state — được set sau khi gửi request
        self.response     = None   # requests.Response
        self.parsed: dict | None = None
        self.elapsed: float | None = None
        self.body_text    = ""
        self.detected_enc = ""
        self.pre_logs: list[str] = []
        self.ai_analysis  = ""

        # Widget references — được set bởi UI khi build tab content
        self._frame       = None   # tk.Frame
        self._curl_tw     = None   # tk.Text
        self._pre_tw      = None   # tk.Text
        self._send_btn    = None   # tk.Button
        self._status_lbl  = None   # tk.Label
        self._env_hint_lbl= None   # tk.Label
        self._nb          = None   # ttk.Notebook
        self._var_ssl     = None   # tk.BooleanVar
        self._var_redirect= None   # tk.BooleanVar
        self._var_decode  = None   # tk.BooleanVar
        self._timeout_var = None   # tk.StringVar
        self._ph_active   = False  # placeholder active flag
