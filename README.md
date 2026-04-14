# ⚡ Curl Runner

> Postman trên Desktop — chạy curl command và xem response trực tiếp, không cần cài Postman.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)
![Version](https://img.shields.io/badge/Version-3.0-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 Screenshot

![Curl Runner Screenshot](screenshot.png)

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| 📑 **Multi-tab** | Mở nhiều request song song, switch qua lại như browser |
| ⚡ **Pre-request Script** | Chạy Python script trước khi gửi — tự động lấy token, set biến |
| ✨ **Beautify Body** | Format JSON body trong curl thành dạng dễ đọc |
| 📋 **History** | Tự động lưu lịch sử request, tìm kiếm, tái sử dụng |
| 🗂 **Collections** | Nhóm và lưu các request hay dùng |
| 🌍 **Environments** | Quản lý biến `{{base_url}}`, `{{token}}` theo từng môi trường |
| 🎨 **JSON Highlight** | Tô màu JSON response (key, string, number, boolean, null) |
| 🔠 **Auto Decode** | Tự detect encoding từ raw bytes — UTF-8, Windows-1252, TIS-620... |
| 💾 **Lưu response** | Export response body ra file `.json` / `.txt` |
| 🖥 **Dark UI** | Giao diện tối theo phong cách Postman |

---

## 🚀 Cài đặt & Chạy

### Yêu cầu
- Python 3.8+
- pip

### Cài thư viện

```bash
pip install requests charset-normalizer
```

### Chạy trực tiếp

```bash
python curl_runner_gui.py
```

### Đóng gói thành `.exe` (không cần Python)

```bash
pip install pyinstaller
python -m PyInstaller --onefile --noconsole --name CurlRunner curl_runner_gui.py
```

File `.exe` xuất ra tại `dist\CurlRunner.exe` — double-click là chạy.

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
- ✅ **Bật** — tự detect encoding từ raw bytes (charset-normalizer), ưu tiên charset từ Content-Type header
- ☐ **Tắt** — trả nguyên raw bytes (latin-1), không mất ký tự, dùng khi debug encoding

Encoding đang dùng hiển thị trong tab **Request Info**.

---

## 📁 Cấu trúc project

```
Curl-runner/
├── curl_runner_gui.py   # GUI desktop (tkinter) — v3
├── curl_runner.py       # CLI version (terminal)
├── build_exe.bat        # Script đóng gói .exe
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

## 🖥 CLI Version

Ngoài GUI, project còn có CLI chạy trên terminal:

```bash
# Paste curl trực tiếp
python curl_runner.py "curl https://httpbin.org/get"

# Import từ file
python curl_runner.py -f request.txt

# Lưu response ra file
python curl_runner.py -f request.txt -o response.json

# Interactive mode (paste rồi Enter 2 lần)
python curl_runner.py

# Xem hướng dẫn
python curl_runner.py --help
```

---

## 📦 Dependencies

| Thư viện | Mục đích |
|---|---|
| `requests` | Gửi HTTP request |
| `charset-normalizer` | Auto-detect encoding của response |
| `pyinstaller` | Đóng gói thành `.exe` (tuỳ chọn) |
| `tkinter` | GUI (có sẵn trong Python) |

---

## 🗺 Roadmap

- [x] Chạy curl command
- [x] History, Collections, Environments
- [x] Multi-tab request
- [x] Pre-request Script
- [x] Beautify JSON body
- [ ] So sánh 2 response (diff)
- [ ] Tìm kiếm trong response (Ctrl+F)
- [ ] AI phân tích lỗi response

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
