@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Missing .venv. Run: python -m venv .venv
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" -m pytest %*
