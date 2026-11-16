@echo off
REM Starts the backend (port 8730) and frontend (port 5730) in two windows, then opens the browser.
REM Uncommon ports so JobFinder does not clash with other dev servers (5173 / 8000).
cd /d "%~dp0"
if not exist backend\.venv (echo Run setup.bat first. & pause & exit /b 1)
if not exist frontend\node_modules (echo Run setup.bat first. & pause & exit /b 1)

netstat -ano | findstr /R /C:":8730 .*LISTENING" >nul && (echo Port 8730 is already in use - is JobFinder already running? & pause & exit /b 1)
netstat -ano | findstr /R /C:":5730 .*LISTENING" >nul && (echo Port 5730 is already in use - is JobFinder already running? & pause & exit /b 1)

start "JobFinder backend" /D "%~dp0backend" cmd /k ".venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8730"
start "JobFinder frontend" /D "%~dp0frontend" cmd /k "npm run dev"

REM Wait until the frontend answers (max ~30 s), then open it.
powershell -NoProfile -Command "for($i=0;$i -lt 60;$i++){ try { Invoke-WebRequest 'http://localhost:5730' -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }"
start "" http://localhost:5730
