# ⚡ Curl Runner

> Postman trên Desktop — chạy curl command và xem response trực tiếp, không cần cài Postman.

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-blue?logo=windows)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 Screenshot

![Curl Runner Screenshot](screenshot.png)

---

## ✨ Tính năng

| Tính năng | Mô tả |
|---|---|
| ⚡ **Chạy curl** | Paste hoặc import curl command, nhấn Send — xem response như Postman |
| 📋 **History** | Tự động lưu lịch sử request, tìm kiếm, tái sử dụng |
| 🗂 **Collections** | Nhóm và lưu các request hay dùng |
| 🌍 **Environments** | Quản lý biến `{{base_url}}`, `{{token}}` theo từng môi trường |
| 🎨 **JSON Highlight** | Tô màu JSON response (key, string, number, boolean, null) |
| 🔠 **Auto Decode** | Tự detect encoding từ raw bytes — hỗ trợ UTF-8, Windows-1252, TIS-620... |
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

### Chạy curl cơ bản

Paste curl command vào ô nhập rồi nhấn **▶ SEND REQUEST**:

```bash
curl https://httpbin.org/get

curl -X POST https://api.example.com/login \
  -H 'Content-Type: application/json' \
  -d '{"user":"admin","pass":"123"}'
```

### Import từ file

Nhấn **📂 Import File** → chọn file `.txt` hoặc `.sh` chứa curl command.

> **Tip:** Copy curl từ Chrome DevTools → chuột phải request → *Copy as cURL*

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

1. Nhấn **➕ Lưu vào Collection** để lưu curl đang soạn
2. Sidebar trái → tab **🗂 Collections** → double-click để load lại
3. Chuột phải → Đổi tên / Xóa

### Auto Decode

Checkbox **Auto Decode** ở hàng options:
- ✅ **Bật** — tự detect encoding từ raw bytes (charset-normalizer), ưu tiên charset từ header
- ☐ **Tắt** — trả nguyên raw bytes (latin-1), không mất ký tự, dùng khi debug encoding

---

## 📁 Cấu trúc project

```
Curl-runner/
├── curl_runner_gui.py   # GUI desktop (tkinter)
├── curl_runner.py       # CLI version (terminal)
├── build_exe.bat        # Script đóng gói .exe
└── README.md
```

### Dữ liệu được lưu tại

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
| `\` (xuống dòng) | Curl nhiều dòng |
| `{{variable}}` | Biến môi trường |

---

## 🛠 CLI Version

Ngoài GUI, project còn có CLI chạy trên terminal:

```bash
# Paste curl trực tiếp
python curl_runner.py "curl https://httpbin.org/get"

# Import từ file
python curl_runner.py -f request.txt

# Lưu response ra file
python curl_runner.py -f request.txt -o response.json

# Interactive mode
python curl_runner.py
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
