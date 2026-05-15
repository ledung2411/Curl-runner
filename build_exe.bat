@echo off
:: Build CurlRunner.exe from the current modular entry point.
:: Requires Python 3.10+ and pip.

echo.
echo  [1/3] Installing required packages...
if exist requirements.txt (
    pip install -r requirements.txt --quiet
) else (
    pip install requests charset-normalizer ttkbootstrap pyinstaller --quiet
)

echo.
echo  [2/3] Building executable. This can take 1-2 minutes...
python -m PyInstaller CurlRunner.spec

echo.
echo  [3/3] Done.
echo  Output file: dist\CurlRunner.exe
echo.
pause
