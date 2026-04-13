@echo off
:: ─────────────────────────────────────────────────────
:: build_exe.bat — Đóng gói curl_runner_gui.py thành .exe
:: Yêu cầu: Python 3.8+, pip
:: ─────────────────────────────────────────────────────

echo.
echo  [1/3] Cai dat thu vien can thiet...
pip install requests pyinstaller --quiet

echo.
echo  [2/3] Dang dong goi thanh .exe (co the mat 1-2 phut)...
pyinstaller --onefile --noconsole --name "CurlRunner" curl_runner_gui.py

echo.
echo  [3/3] Hoan thanh!
echo  File .exe nam tai: dist\CurlRunner.exe
echo.
pause
