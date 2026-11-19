@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv...
  python -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt -r requirements-dev.txt
if errorlevel 1 exit /b 1

if exist "requirements-desktop.txt" (
  echo Installing desktop dependencies...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-desktop.txt
  if errorlevel 1 exit /b 1
)

echo.
echo Done. Next: .\run-tests.bat
