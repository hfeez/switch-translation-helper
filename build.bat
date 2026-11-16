@echo off
REM Build Windows. Pakai:  build.bat        (folder, startup cepat)
REM                        build.bat onefile (satu .exe)
setlocal
if not exist .venv ( python -m venv .venv || goto :err )
call .venv\Scripts\activate || goto :err
python -m pip install -q -r requirements.txt pyinstaller || goto :err
python -m unittest discover -s tests || goto :err
set MODE=--onedir
if "%1"=="onefile" set MODE=--onefile
pyinstaller --noconfirm --clean --windowed %MODE% --name SwitchTranslationHelper main.py || goto :err
echo.
echo Selesai. Lihat folder dist\
exit /b 0
:err
echo BUILD GAGAL
exit /b 1
