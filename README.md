# ⚡ Curl Runner

> Postman trên Desktop — chạy curl command và xem response trực tiếp, không cần cài Postman.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)
![Version](https://img.shields.io/badge/Version-4.0-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 Screenshot

![Curl Runner Screenshot](screenshotv3.png)

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| 📑 **Multi-tab** | Mở nhiều request song song, switch qua lại như browser |
| ⚡ **Pre-request Script** | Chạy Python script trước khi gửi — tự động lấy token, set biến |
| ✨ **Beautify Body** | Format JSON body trong curl thành dạng dễ đọc |
| ⇄ **So sánh Curl** | Highlight điểm khác nhau giữa n curl, panel kéo thả resize |
| 📋 **History** | Tự động lưu lịch sử request, tìm kiếm, tái sử dụng |
| 🗂 **Collections** | Nhóm và lưu các request hay dùng |
| 🌍 **Environments** | Quản lý biến `{{base_url}}`, `{{token}}` theo từng môi trường |
| 🎨 **JSON Highlight** | Tô màu JSON response (key, string, number, boolean, null) |
| 🔎 **Response Search** | Tìm kiếm trong Body / Headers / Info / Log / AI bằng `Ctrl+F`, highlight và Next/Prev |
| 🤖 **AI phân tích lỗi** | Dùng Ollama local miễn phí để đọc response, tìm lỗi/bug và gợi ý cách xử lý |
| 🚀 **Large response friendly** | Giới hạn preview và bỏ syntax highlight khi response quá lớn để UI không bị lag |
| 🔠 **Auto Decode** | Tự detect encoding từ raw bytes — UTF-8, Windows-1252, TIS-620... |
| 💾 **Lưu response** | Export response body ra file `.json` / `.txt` |
| 🖥 **Dark UI** | Giao diện tối theo phong cách Postman |

---

## 🚀 Cài đặt & Chạy

### Yêu cầu
- Python 3.8+
- pip
- Ollama nếu muốn dùng AI analysis local miễn phí

### Cài thư viện Python

```bash
pip install requests charset-normalizer
```

Nếu muốn đóng gói `.exe`, cài thêm:

```bash
pip install pyinstaller
```

### Chạy nhanh từ source

```bash
git clone https://github.com/ledung2411/Curl-runner.git
cd Curl-runner
pip install requests charset-normalizer
python main.py
```

### Chạy trực tiếp

```bash
python main.py
```

### Đóng gói thành `.exe` (không cần Python)

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name CurlRunner main.py
```

File `.exe` xuất ra tại `dist\CurlRunner.exe` — double-click là chạy.

Hoặc dùng script có sẵn:

```bat
build_exe.bat
```

---

## 📖 Hướng dẫn sử dụng

### Multi-tab

- Nhấn **＋** trên tab bar để mở tab mới
- **Double-click** tên tab để đổi tên
- **✕** để đóng tab (giữ ít nhất 1 tab)
- Chuột phải vào History hoặc Collection → **"Mở trong tab mới"**
- Mỗi tab có curl input, options, pre-script và response riêng biệt

### Chạy curl cơ bản

Paste curl command vào ô nhập rồi nhấn **▶ SEND REQUEST**:

```bash
curl https://httpbin.org/get

curl -X POST https://api.example.com/login \
  -H 'Content-Type: application/json' \
  -d '{"user":"admin","pass":"123"}'
```

> **Tip:** Copy curl từ Chrome DevTools → chuột phải request → *Copy as cURL*

### So sánh Curl (⇄ Compare)

Nhấn **⇄ Compare** trên topbar để mở popup so sánh.

**Cấu trúc popup:**
- Các panel nằm ngang, **kéo thanh phân cách để resize**
- Mỗi panel gồm 2 vùng kéo thả: **INPUT** (paste curl) và **DIFF VIEW** (highlight)
- Nút **＋ Thêm panel** để thêm curl cần so sánh
- Nút **📋 Từ tab mở** để nạp tự động từ các tab đang mở

**Màu sắc highlight:**

| Màu | Ý nghĩa |
|---|---|
| 🟢 Xanh lá | Dòng chỉ xuất hiện ở panel này |
| 🟡 Vàng | Dòng tồn tại nhưng giá trị khác |
| 🔴 Đỏ nhạt | Dòng trống (padding để align) |
| Bình thường | Giống nhau ở tất cả panels |

So sánh **semantic** — parse curl ra cấu trúc `Method / URL / Header / Body / Option` thay vì so raw text, nên thứ tự flag khác nhau vẫn phát hiện đúng điểm khác biệt.

### Beautify Body

Nhấn **✨ Beautify** để format JSON body trong curl thành dạng dễ đọc:

```bash
# Trước
curl -X POST https://api.example.com/users \
  -d '{"name":"Nguyen Van A","age":30,"city":"HCM"}'

# Sau khi Beautify
curl -X POST https://api.example.com/users \
  -d '{
  "name": "Nguyen Van A",
  "age": 30,
  "city": "HCM"
}'
```

### Pre-request Script

Mỗi tab có sub-tab **⚡ Pre-request Script** để viết Python chạy trước khi gửi request.

**API có sẵn:**

| Hàm | Mô tả |
|---|---|
| `set_env('key', 'value')` | Set biến environment |
| `env['key'] = 'value'` | Cách khác để set biến |
| `log('message')` | In ra Script Log tab |
| `requests` | Thư viện requests để gọi API khác |
| `json`, `re` | Thư viện Python thông dụng |

**Ví dụ — Tự động lấy token trước khi gửi:**

```python
# Gọi API login để lấy token
resp = requests.post(env.get('base_url','') + '/auth/login',
    json={'username': 'admin', 'password': 'secret'},
    timeout=10)

if resp.ok:
    token = resp.json()['data']['token']
    set_env('token', token)
    log(f'Token: {token[:20]}...')
else:
    log(f'Login thất bại: {resp.status_code}')
```

```python
# Set timestamp động
import time
set_env('timestamp', str(int(time.time())))
```

Kết quả script hiển thị ở tab **Script Log** trên response panel.

### Dùng biến môi trường

Khai báo biến trong **⚙ Manage Environments**:

| Variable | Value |
|---|---|
| `base_url` | `https://api.example.com` |
| `token` | `eyJhbGciOiJIUzI1...` |

Sau đó dùng trong curl:

```bash
curl {{base_url}}/api/users \
  -H 'Authorization: Bearer {{token}}'
```

Indicator real-time hiện bên cạnh: `✓ base_url, token` nếu đã khai báo, `✗ token` nếu thiếu.

### Collections

1. Nhấn **➕ Collection** để lưu curl đang soạn
2. Sidebar trái → tab **🗂 Collections** → double-click để load lại
3. Chuột phải → Đổi tên / Xóa / Mở trong tab mới

### Auto Decode

Checkbox **Auto Decode** ở hàng options:
- ✅ **Bật** — tự detect encoding từ raw bytes, ưu tiên charset từ Content-Type header
- ☐ **Tắt** — trả nguyên raw bytes (latin-1), dùng khi debug encoding

Encoding đang dùng hiển thị trong tab **Request Info**.

### Tìm kiếm trong response

Response panel có thanh **Search** để tìm trong tab đang mở:

- Nhấn `Ctrl+F` để focus vào ô search
- `Enter` để tới kết quả tiếp theo
- `Shift+Enter` hoặc **Prev** để quay lại kết quả trước
- Bật **Aa** để phân biệt hoa/thường
- Hoạt động với **Body**, **Headers**, **Info**, **Log** và **AI**
- Mỗi response tab có kết quả riêng; đổi tab sẽ chạy lại search trên tab đó
- Nếu có quá nhiều kết quả, app chỉ highlight một phần đầu để giữ UI mượt

### AI phân tích lỗi response

Nhấn **AI Analyze** sau khi gửi request để AI đọc request/response đã được redact và đưa ra:

- Tóm tắt tình trạng response
- Bằng chứng lỗi từ status/header/body
- Nguyên nhân có khả năng cao
- Gợi ý sửa API/client/request
- Các bước kiểm tra tiếp theo

Mặc định app dùng **Ollama local** nên không cần billing API, không cần OpenAI key và dữ liệu phân tích chạy trên máy của bạn.

#### Cài Ollama local

```powershell
winget install --id Ollama.Ollama -e
ollama pull llama3.2
```

Sau khi cài xong, mở lại terminal/app nếu lệnh `ollama` chưa nhận ngay.

Kiểm tra Ollama đang chạy:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

Nếu lệnh trên trả về danh sách model, **AI Analyze** đã sẵn sàng.

#### Chọn model Ollama khác

Bạn có thể dùng model nhẹ hơn hoặc model bạn đã cài:

```powershell
ollama pull qwen2.5
setx OLLAMA_MODEL "qwen2.5"
```

App sẽ tự chọn model đã cài theo thứ tự ưu tiên: `llama3.2`, `llama3.1`, `gemma3`, `mistral`, `qwen2.5`. Nếu không có model nào, app sẽ báo cần chạy `ollama pull llama3.2`.

#### Dùng OpenAI thay cho Ollama

OpenAI API là tuỳ chọn và thường cần billing riêng trên OpenAI Platform.

```powershell
setx AI_PROVIDER "openai"
setx OPENAI_API_KEY "sk-..."
setx OPENAI_MODEL "gpt-5.4-mini"
```

Để quay lại Ollama:

```powershell
setx AI_PROVIDER "ollama"
```

Tuỳ chọn cấu hình:

| Biến môi trường | Mô tả |
|---|---|
| `OLLAMA_MODEL` | Chọn model local, ví dụ `llama3.2` |
| `OLLAMA_BASE_URL` | Đổi endpoint Ollama, mặc định `http://localhost:11434` |
| `AI_PROVIDER=openai` | Dùng OpenAI API thay vì Ollama |
| `OPENAI_API_KEY` | API key khi dùng OpenAI |
| `OPENAI_MODEL` | Model OpenAI, mặc định `gpt-5.4-mini` |

Trước khi gửi nội dung cho AI, app tự redact các header/body nhạy cảm như `Authorization`, `Cookie`, token, API key, password và secret. Redaction là best-effort, vì vậy vẫn nên tránh gửi response thật có dữ liệu khách hàng/production secret vào provider bên ngoài.

#### Lỗi thường gặp với AI Analyze

| Lỗi | Cách xử lý |
|---|---|
| `Cannot connect to Ollama` | Cài Ollama, mở Ollama app/service, rồi chạy `ollama pull llama3.2` |
| `No Ollama models installed` | Chạy `ollama pull llama3.2` |
| `model is not installed` | Chạy `ollama pull <model>` hoặc xoá/sửa `OLLAMA_MODEL` |
| OpenAI `401` | Kiểm tra `OPENAI_API_KEY` |
| OpenAI billing/quota | Thêm billing/credits hoặc quay lại `AI_PROVIDER=ollama` |

### Large response performance

Để tránh lag khi response rất lớn:

- App giới hạn preview body trong UI nhưng vẫn lưu full raw response khi bấm **Save**
- JSON nhỏ được format và highlight màu
- JSON quá lớn vẫn được format/hiển thị nhưng bỏ highlight chi tiết để tăng tốc
- Search giới hạn số vùng highlight để không làm Tkinter bị chậm

---

## 📁 Cấu trúc project

```
Curl-runner/
├── main.py              # Entry point
├── app.py               # Tkinter GUI
├── core.py              # Parse curl, execute request, decode, AI analysis
├── models.py            # Tab/request state
├── store.py             # History, collections, environments
├── constants.py         # Theme, colors, fonts
├── ui_compare.py        # Compare curl popup
├── ui_widgets.py        # Shared UI widgets
├── CurlRunner.spec      # PyInstaller spec
└── README.md
```

### Dữ liệu lưu tại

```
C:\Users\<tên>\.curl_runner\
├── history.json         # Lịch sử request (tối đa 500)
├── collections.json     # Collections
└── environments.json    # Environments & variables
```

---

## ⚙️ Các flag curl được hỗ trợ

| Flag | Mô tả |
|---|---|
| `-X GET/POST/PUT/DELETE...` | Chỉ định HTTP method |
| `-H 'Key: Value'` | Thêm request header |
| `-d '...'` / `--data-raw` | Request body |
| `--data-binary` | Binary body |
| `-F key=value` | Form data (multipart) |
| `-u user:pass` | Basic Authentication |
| `-k` / `--insecure` | Bỏ qua kiểm tra SSL |
| `-L` / `--location` | Follow redirect |
| `-m` / `--max-time` | Timeout (giây) |
| `\` / `^` (xuống dòng) | Curl nhiều dòng (Linux/Windows) |
| `{{variable}}` | Biến môi trường |

---

## 🛠 Cấu hình VS Code

Thêm vào `.vscode/settings.json` để tắt Pylance warnings với tkinter:

```json
{
  "python.analysis.diagnosticSeverityOverrides": {
    "reportUnknownMemberType": "none",
    "reportUnknownVariableType": "none",
    "reportUnknownArgumentType": "none"
  }
}
```

---

## 📦 Dependencies

| Thư viện | Mục đích |
|---|---|
| `requests` | Gửi HTTP request |
| `charset-normalizer` | Auto-detect encoding của response |
| `pyinstaller` | Đóng gói thành `.exe` (tuỳ chọn) |
| `tkinter` | GUI (có sẵn trong Python) |
| Ollama desktop/service | AI analysis local miễn phí (tuỳ chọn, chạy ngoài Python) |

---

## 🗺 Roadmap

- [x] Chạy curl command
- [x] History, Collections, Environments
- [x] Multi-tab request
- [x] Pre-request Script
- [x] Beautify JSON body
- [x] So sánh Curl (diff n panels)
- [x] Tìm kiếm trong response (Ctrl+F)
- [x] AI phân tích lỗi response bằng Ollama local

---

## 🤝 Contributing

Pull request và issue luôn được chào đón!

1. Fork repo
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m 'Add: mô tả tính năng'`
4. Push: `git push origin feature/ten-tinh-nang`
5. Mở Pull Request

---

## 📄 License

MIT License — free to use, modify, and distribute.
