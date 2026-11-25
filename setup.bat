@echo off
REM First-time install: Python venv + backend packages, frontend packages, Chromium for PDFs.
REM JOBFINDER_NO_PAUSE=1 skips the "press a key" pauses (used by the automatic Windows install check).
setlocal
cd /d "%~dp0"

where python >nul 2>nul || (echo Python 3.11+ is required: https://www.python.org/downloads/ & goto :fail)
where npm >nul 2>nul || (echo Node.js 20+ is required: https://nodejs.org/ & goto :fail)

if not exist backend\.venv (
  echo Creating Python virtual environment...
  python -m venv backend\.venv || goto :fail
)
echo Installing backend packages...
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt || goto :fail

echo Installing frontend packages...
pushd frontend
call npm install || (popd & goto :fail)
popd

echo Installing Chromium for PDF export (Playwright)...
backend\.venv\Scripts\python -m playwright install chromium || goto :fail

if not exist data mkdir data
echo.
echo Setup complete. Run start.bat to launch JobFinder.
if not "%JOBFINDER_NO_PAUSE%"=="1" pause
exit /b 0

:fail
echo.
echo Setup did not finish. Read the message above, fix it, then run setup.bat again.
echo If it mentions "Long Path" or a missing file deep in a folder, the JobFinder folder's path is too long:
echo move the folder somewhere short (for example C:\JobFinder) and run setup.bat again.
if not "%JOBFINDER_NO_PAUSE%"=="1" pause
exit /b 1
