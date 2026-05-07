#!/usr/bin/env python3
"""
main.py — Entry point cho Curl Runner

Chạy   : python main.py
Đóng gói: python -m PyInstaller --onefile --noconsole --name CurlRunner main.py
"""

from app import CurlRunnerApp

if __name__ == "__main__":
    app = CurlRunnerApp()
    app.mainloop()
