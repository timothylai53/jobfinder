@echo off
REM Starts JobFinder: backend (127.0.0.1:8730) and frontend (localhost:5730) together in ONE minimized window,
REM then opens the browser. To stop: run stop.bat, or close the "JobFinder" window on the taskbar.
REM To see both logs in separate windows, use start-debug.bat instead.
cd /d "%~dp0"
if not exist backend\.venv (echo Run setup.bat first. & pause & exit /b 1)
if not exist frontend\node_modules (echo Run setup.bat first. & pause & exit /b 1)

netstat -ano | findstr /R /C:":8730 .*LISTENING" >nul && (echo JobFinder already seems to be running ^(port 8730 in use^). Opening it. & start "" http://localhost:5730 & exit /b 0)
netstat -ano | findstr /R /C:":5730 .*LISTENING" >nul && (echo Port 5730 is in use by another program. Run stop.bat or close it first. & pause & exit /b 1)

start "JobFinder" /min "%~dp0scripts\run-servers.cmd"

REM Wait until the frontend answers (max ~30 s), then open it. JOBFINDER_NO_BROWSER=1 skips this (used for checks).
powershell -NoProfile -Command "for($i=0;$i -lt 60;$i++){ try { Invoke-WebRequest 'http://localhost:5730' -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }"
if not "%JOBFINDER_NO_BROWSER%"=="1" start "" http://localhost:5730
