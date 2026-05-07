@echo off
:: Build CurlRunner.exe from the current modular entry point.
:: Requires Python 3.8+ and pip.

echo.
echo  [1/3] Installing required packages...
pip install requests charset-normalizer pyinstaller --quiet

echo.
echo  [2/3] Building executable. This can take 1-2 minutes...
python -m PyInstaller --onefile --noconsole --name "CurlRunner" main.py

echo.
echo  [3/3] Done.
echo  Output file: dist\CurlRunner.exe
echo.
pause
