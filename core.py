# core.py — Business logic: parse curl, execute request, pre-script, decode, beautify
# type: ignore
from __future__ import annotations

import re
import json
import shlex
import time
from typing import Any

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests  # type: ignore

try:
    from charset_normalizer import from_bytes as _detect_encoding
    HAS_DETECT = True
except ImportError:
    try:
        from chardet import detect as _chardet_detect  # type: ignore
        def _detect_encoding(raw: bytes):              # type: ignore
            class _R:
                best = type("B", (), {
                    "encoding": _chardet_detect(raw).get("encoding", "utf-8")
                })()
            return _R()
        HAS_DETECT = True
    except ImportError:
        HAS_DETECT = False


AI_ANALYSIS_BODY_LIMIT = 12_000
AI_ANALYSIS_REQUEST_BODY_LIMIT = 4_000
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"
OLLAMA_FALLBACK_MODELS = ("llama3.2", "llama3.1", "gemma3", "mistral", "qwen2.5")
SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|set-cookie|token|secret|password|passwd|api[-_ ]?key|x-api-key|access[_-]?token|refresh[_-]?token|jwt)",
    re.I,
)


def redact_sensitive_text(text: str) -> str:
    """Best-effort redaction before sending request/response context to an AI model."""
    if not text:
        return ""
    text = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1[REDACTED]", text)
    text = re.sub(
        r"(?i)(\"?(?:access_token|refresh_token|token|api_key|apikey|secret|password|passwd)\"?\s*[:=]\s*\"?)[^\",\s}\]]+(\"?)",
        r"\1[REDACTED]\2",
        text,
    )
    lines = []
    for line in text.splitlines():
        head = line.split(":", 1)[0].split("=", 1)[0]
        if SENSITIVE_KEY_RE.search(head):
            if ":" in line:
                key, _, _ = line.partition(":")
                lines.append(f"{key}: [REDACTED]")
            elif "=" in line:
                key, _, _ = line.partition("=")
                lines.append(f"{key}=[REDACTED]")
            else:
                lines.append("[REDACTED]")
        else:
            lines.append(line)
    return "\n".join(lines)


def _redact_headers(headers: dict | Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in dict(headers or {}).items():
        out[str(k)] = "[REDACTED]" if SENSITIVE_KEY_RE.search(str(k)) else str(v)
    return out


def build_ai_response_context(parsed: dict, resp, body_text: str, enc_info: str) -> str:
    """Build a compact, redacted prompt context for response debugging."""
    request_body = parsed.get("body") if parsed else None
    if isinstance(request_body, bytes):
        request_body_text = f"[binary body: {len(request_body):,} bytes]"
    elif request_body is None:
        request_body_text = ""
    else:
        request_body_text = redact_sensitive_text(str(request_body))[:AI_ANALYSIS_REQUEST_BODY_LIMIT]

    body_preview = redact_sensitive_text(body_text or "")
    truncated = ""
    if len(body_preview) > AI_ANALYSIS_BODY_LIMIT:
        truncated = f"\n[Response body truncated from {len(body_preview):,} characters.]"
        body_preview = body_preview[:AI_ANALYSIS_BODY_LIMIT]

    context = {
        "request": {
            "method": (parsed or {}).get("method"),
            "url": (parsed or {}).get("url"),
            "headers": _redact_headers((parsed or {}).get("headers", {})),
            "body_preview": request_body_text,
        },
        "response": {
            "status": f"{getattr(resp, 'status_code', '?')} {getattr(resp, 'reason', '')}".strip(),
            "headers": _redact_headers(getattr(resp, "headers", {})),
            "encoding": enc_info,
            "size_bytes": len(getattr(resp, "content", b"") or b""),
            "body_preview": body_preview + truncated,
        },
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def _extract_response_text(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    parts: list[str] = []
    for item in data.get("output", []) or []:
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) or []:
            if isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def _openai_error_message(status_code: int, body_text: str, data: dict | None) -> str:
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict):
            for key in ("message", "code", "type"):
                value = err.get(key)
                if value:
                    return str(value)
        elif err:
            return str(err)
    snippet = (body_text or "").strip()
    if snippet:
        return snippet[:800]
    return f"HTTP {status_code} with an empty response body"


def analyze_response_with_ai(api_key: str, context_json: str, model: str = "gpt-5.4-mini") -> str:
    """Call the OpenAI Responses API and return an API debugging report."""
    payload = {
        "model": model,
        "store": False,
        "max_output_tokens": 1200,
        "instructions": (
            "Respond in Vietnamese. Use clear, practical Vietnamese for developers. "
            "You are a senior API debugging assistant. Analyze the HTTP response and "
            "request context. Identify likely backend/client bugs, bad input, auth issues, "
            "schema mismatches, timeout/rate-limit clues, and suspicious response content. "
            "If the response appears healthy, say that clearly. Keep the answer concise "
            "with sections: Summary, Evidence, Likely cause, Suggested fixes, Next checks."
        ),
        "input": (
            "Analyze this redacted HTTP request/response context for errors or bugs. "
            "Do not reveal or reconstruct secrets.\n\n"
            f"{context_json}"
        ),
    }
    try:
        r = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=90,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach OpenAI API: {exc}") from exc

    raw_text = r.text or ""
    try:
        data = r.json()
    except Exception:
        data = None
    if r.status_code >= 400:
        msg = _openai_error_message(r.status_code, raw_text, data if isinstance(data, dict) else None)
        raise RuntimeError(f"OpenAI API error ({r.status_code}): {msg}")
    text = _extract_response_text(data if isinstance(data, dict) else {})
    if not text:
        snippet = raw_text[:800].strip()
        detail = f" Response body: {snippet}" if snippet else ""
        raise RuntimeError(f"OpenAI API returned no analysis text.{detail}")
    return text


def list_ollama_models(base_url: str = OLLAMA_DEFAULT_BASE_URL) -> list[str]:
    """Return locally installed Ollama model names."""
    base = base_url.rstrip("/")
    try:
        r = requests.get(f"{base}/api/tags", timeout=5)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        raise RuntimeError(
            "Cannot connect to Ollama. Install and start Ollama, then run `ollama pull llama3.2`."
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"Ollama returned an invalid model list: {exc}") from exc

    models = []
    for item in data.get("models", []) if isinstance(data, dict) else []:
        name = item.get("name") if isinstance(item, dict) else None
        if name:
            models.append(str(name))
    return models


def choose_ollama_model(preferred_model: str = "", base_url: str = OLLAMA_DEFAULT_BASE_URL) -> str:
    models = list_ollama_models(base_url)
    if preferred_model:
        if preferred_model in models:
            return preferred_model
        raise RuntimeError(
            f"Ollama model `{preferred_model}` is not installed. Run `ollama pull {preferred_model}`."
        )
    if not models:
        raise RuntimeError("No Ollama models installed. Run `ollama pull llama3.2` first.")

    for candidate in OLLAMA_FALLBACK_MODELS:
        for installed in models:
            if installed == candidate or installed.startswith(candidate + ":"):
                return installed
    return models[0]


def analyze_response_with_ollama(
    context_json: str,
    model: str = "",
    base_url: str = OLLAMA_DEFAULT_BASE_URL,
) -> tuple[str, str]:
    """Analyze a response through a local Ollama model. Returns (report, model_used)."""
    base = base_url.rstrip("/")
    model_used = choose_ollama_model(model, base)
    prompt = (
        "Respond in Vietnamese. Use clear, practical Vietnamese for developers. "
        "You are a senior API debugging assistant. Analyze the redacted HTTP "
        "request/response context below. Identify likely backend/client bugs, bad input, "
        "auth issues, schema mismatches, timeout/rate-limit clues, and suspicious response "
        "content. If the response appears healthy, say that clearly. Keep the answer concise "
        "with sections: Summary, Evidence, Likely cause, Suggested fixes, Next checks. "
        "Do not reveal or reconstruct secrets.\n\n"
        f"{context_json}"
    )
    payload = {
        "model": model_used,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 1000,
        },
    }
    try:
        r = requests.post(f"{base}/api/generate", json=payload, timeout=180)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Ollama generate API: {exc}") from exc

    raw_text = r.text or ""
    try:
        data = r.json()
    except Exception as exc:
        raise RuntimeError(f"Ollama returned invalid JSON: {raw_text[:500] or exc}") from exc
    if r.status_code >= 400:
        msg = data.get("error") if isinstance(data, dict) else raw_text[:500]
        raise RuntimeError(f"Ollama API error ({r.status_code}): {msg or 'empty error body'}")
    text = data.get("response", "") if isinstance(data, dict) else ""
    if not str(text).strip():
        raise RuntimeError(f"Ollama returned no analysis text. Response body: {raw_text[:500]}")
    return str(text).strip(), model_used


# ──────────────────────────────────────────────
# Environment variable substitution
# ──────────────────────────────────────────────
def apply_env(text: str, env: dict[str, str]) -> str:
    """Thay thế {{key}} bằng giá trị trong env dict."""
    for k, v in env.items():
        text = text.replace("{{" + k + "}}", v)
    return text


# ──────────────────────────────────────────────
# Pre-request script
# ──────────────────────────────────────────────
def run_pre_script(script: str, env: dict[str, str]) -> tuple[dict, list[str]]:
    """
    Chạy pre-request Python script trong sandbox an toàn.

    API dùng được trong script:
      set_env('key', 'value')  → set biến env
      env['key'] = 'value'     → cách khác
      log('message')           → ghi vào Script Log tab
      requests / json / re     → thư viện sẵn có

    Returns:
        (env_updated, logs)
    """
    logs      = []
    local_env = dict(env)

    def set_env(k: str, v: Any) -> None:
        local_env[k] = str(v)
        logs.append(f"✓ set_env({k!r}, {str(v)[:40]!r})")

    def log(msg: Any) -> None:
        logs.append(f"  {msg}")

    sandbox = {
        "env":      local_env,
        "set_env":  set_env,
        "log":      log,
        "requests": requests,
        "json":     json,
        "re":       re,
    }
    try:
        exec(compile(script, "<pre-request>", "exec"), sandbox)
        for k, v in sandbox["env"].items():
            local_env[k] = v
        logs.insert(0, "✅ Script chạy thành công")
    except Exception as e:
        logs.insert(0, f"❌ Script lỗi: {e}")

    return local_env, logs


# ──────────────────────────────────────────────
# Curl parser
# ──────────────────────────────────────────────
def parse_curl(curl_string: str) -> dict:
    """
    Parse chuỗi curl thành dict:
      method, url, headers, body, auth,
      verify_ssl, allow_redirects, timeout
    """
    curl_string = re.sub(r'\\\s*\n\s*', ' ', curl_string)
    curl_string = re.sub(r'\^\s*\n\s*', ' ', curl_string)
    curl_string = curl_string.strip()

    try:
        tokens = shlex.split(curl_string)
    except ValueError as e:
        raise ValueError(f"Không thể parse curl: {e}")

    if not tokens or tokens[0].lower() != 'curl':
        raise ValueError("Chuỗi phải bắt đầu bằng 'curl'")

    r: dict[str, Any] = {
        "method": None, "url": None, "headers": {}, "body": None,
        "auth": None, "verify_ssl": True, "allow_redirects": True, "timeout": 30,
    }
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
        elif t in ('-k', '--insecure'):
            r["verify_ssl"] = False
        elif t in ('-L', '--location'):
            r["allow_redirects"] = True
        elif t == '--url':
            i += 1; r["url"] = tokens[i]
        elif t in ('--max-time', '-m'):
            i += 1
            try: r["timeout"] = float(tokens[i])
            except Exception: pass
        elif t == '--oauth2-bearer':
            i += 1; r["headers"]["Authorization"] = f"Bearer {tokens[i]}"
        i += 1

    if r["url"] is None:    raise ValueError("Không tìm thấy URL trong chuỗi curl")
    if r["method"] is None: r["method"] = "POST" if r["body"] else "GET"
    return r


# ──────────────────────────────────────────────
# HTTP executor
# ──────────────────────────────────────────────
def execute_request(parsed: dict) -> tuple:
    """Gửi HTTP request, trả về (response, elapsed_ms)."""
    kwargs: dict[str, Any] = {
        "headers": parsed["headers"],
        "auth":    parsed["auth"],
        "verify":  parsed["verify_ssl"],
        "allow_redirects": parsed["allow_redirects"],
        "timeout": parsed["timeout"],
    }
    body = parsed["body"]
    if isinstance(body, dict):
        kwargs["files"] = body
    elif isinstance(body, str):
        ct = parsed["headers"].get("Content-Type",
             parsed["headers"].get("content-type", ""))
        if "application/json" in ct:
            try:    kwargs["json"] = json.loads(body)
            except Exception: kwargs["data"] = body
        else:
            kwargs["data"] = body
    elif isinstance(body, bytes):
        kwargs["data"] = body

    t0   = time.time()
    resp = requests.request(parsed["method"], parsed["url"], **kwargs)
    return resp, (time.time() - t0) * 1000


# ──────────────────────────────────────────────
# Response decoder
# ──────────────────────────────────────────────
def decode_response(resp, auto_decode: bool = True) -> tuple[str, str]:
    """
    Decode response body theo thứ tự ưu tiên:
      1. charset từ Content-Type header
      2. Auto-detect qua charset-normalizer / chardet
      3. Fallback UTF-8

    Returns:
        (body_text, encoding_info)
    """
    if not auto_decode:
        return resp.content.decode("latin-1"), "raw (no decode)"

    ct_header     = resp.headers.get("Content-Type", "")
    charset_match = re.search(r'charset=([^\s;]+)', ct_header, re.I)

    if charset_match:
        charset = charset_match.group(1).strip()
        enc_info = f"{charset}  (từ Content-Type header)"
        try:
            return resp.content.decode(charset, errors="replace"), enc_info
        except (LookupError, UnicodeDecodeError):
            return resp.content.decode("utf-8", errors="replace"), enc_info + " → fallback utf-8"

    if HAS_DETECT and resp.content:
        result = _detect_encoding(resp.content)
        best = result.best() if callable(getattr(result, "best", None)) else getattr(result, "best", None)
        charset = getattr(best, "encoding", None) or "utf-8"
        enc_info = f"{charset}  (auto-detected)"
        try:
            return resp.content.decode(charset or "utf-8", errors="replace"), enc_info
        except (LookupError, UnicodeDecodeError):
            return resp.content.decode("utf-8", errors="replace"), "utf-8  (fallback)"

    return resp.content.decode("utf-8", errors="replace"), \
           "utf-8  (fallback — charset-normalizer not installed)"


# ──────────────────────────────────────────────
# Beautify curl body
# ──────────────────────────────────────────────
def beautify_curl_body(curl_str: str) -> str:
    """
    Tìm -d / --data-raw trong curl string.
    Nếu body là JSON hợp lệ → format indent=2.
    Trả về curl string đã format.
    """
    pattern = re.compile(
        r"(-d|--data|--data-raw|--data-binary|--data-ascii)\s+"
        r"('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")",
        re.DOTALL
    )

    def _fmt(m: re.Match) -> str:
        flag  = m.group(1)
        raw   = m.group(2)
        quote = raw[0]
        inner = raw[1:-1].replace(f"\\{quote}", quote)
        try:
            obj        = json.loads(inner)
            pretty     = json.dumps(obj, indent=2, ensure_ascii=False)
            pretty_esc = pretty.replace(quote, f"\\{quote}")
            return f"{flag} {quote}{pretty_esc}{quote}"
        except Exception:
            return m.group(0)

    return pattern.sub(_fmt, curl_str)
