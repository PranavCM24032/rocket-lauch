@echo off
setlocal
echo Building Rocket Launch Game executable...
where pyinstaller >nul 2>nul
if errorlevel 1 (
  echo PyInstaller not found. Installing...
  pip install pyinstaller
)
pyinstaller --onefile --noconsole --name RocketLaunchGame space.py
echo Done. EXE is in dist\RocketLaunchGame.exe
pause
