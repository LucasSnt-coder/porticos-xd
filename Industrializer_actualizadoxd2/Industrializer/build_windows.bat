@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo        INDUSTRIALIZER - COMPILACION WINDOWS
echo ===============================================

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python make_icon.py

pyinstaller --noconfirm --clean --windowed ^
  --name Industrializer ^
  --icon assets\industrializer.ico ^
  --add-data "assets;assets" ^
  main.py

echo.
echo Aplicacion generada en: dist\Industrializer\Industrializer.exe
pause
