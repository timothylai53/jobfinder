@echo off
REM First-time install: Python venv + backend packages, frontend packages.
cd /d "%~dp0"

where python >nul 2>nul || (echo Python 3.11+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & pause & exit /b 1)

if not exist backend\.venv (
  echo Creating Python virtual environment...
  python -m venv backend\.venv || (pause & exit /b 1)
)
echo Installing backend packages...
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || (pause & exit /b 1)

echo Installing frontend packages...
pushd frontend
call npm install || (popd & pause & exit /b 1)
popd

echo Installing Chromium for PDF export (Playwright)...
backend\.venv\Scripts\python -m playwright install chromium || (pause & exit /b 1)

if not exist data mkdir data
echo.
echo Setup complete. Run start.bat to launch JobFinder.
pause
