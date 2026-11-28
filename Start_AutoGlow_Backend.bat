@echo off
cd /d "%~dp0"
echo Starting AutoGlow backend...
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10 or newer and try again.
  pause
  exit /b 1
)
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
start "AutoGlow Backend" cmd /k "python app.py"
timeout /t 3 >nul
start http://127.0.0.1:5000
