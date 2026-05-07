# store.py — Lưu/đọc dữ liệu (history, collections, environments)
# type: ignore
import json
import os
from pathlib import Path

DATA_DIR  = Path(os.path.expanduser("~")) / ".curl_runner"
DATA_DIR.mkdir(exist_ok=True)

HIST_FILE = DATA_DIR / "history.json"
COLL_FILE = DATA_DIR / "collections.json"
ENV_FILE  = DATA_DIR / "environments.json"
SCEN_FILE = DATA_DIR / "scenarios.json"


def load(path: Path, default):
    """Đọc file JSON, trả về default nếu lỗi."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save(path: Path, data) -> None:
    """Ghi dữ liệu ra file JSON."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Convenience wrappers ──────────────────────
def load_history() -> list:
    return load(HIST_FILE, [])

def save_history(data: list) -> None:
    save(HIST_FILE, data)

def load_collections() -> dict:
    return load(COLL_FILE, {})

def save_collections(data: dict) -> None:
    save(COLL_FILE, data)

def load_environments() -> dict:
    return load(ENV_FILE, {"Default": {}})

def save_environments(data: dict) -> None:
    save(ENV_FILE, data)

def load_scenarios() -> list:
    return load(SCEN_FILE, [])

def save_scenarios(data: list) -> None:
    save(SCEN_FILE, data)
