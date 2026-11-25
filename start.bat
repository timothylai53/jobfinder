@echo off
REM Starts JobFinder: backend (127.0.0.1:8730) and frontend (localhost:5730) together in ONE minimized window,
REM then opens the browser. To stop: run stop.bat, or close the "JobFinder" window on the taskbar.
REM To see both logs in separate windows, use start-debug.bat instead.
REM For checks only: JOBFINDER_PORT / JOBFINDER_UI_PORT pick other ports, JOBFINDER_NO_BROWSER=1 skips the browser,
REM JOBFINDER_NO_PAUSE=1 skips pauses, JOBFINDER_LOG_DIR writes both logs to files there.
cd /d "%~dp0"
if "%JOBFINDER_PORT%"=="" set JOBFINDER_PORT=8730
if "%JOBFINDER_UI_PORT%"=="" set JOBFINDER_UI_PORT=5730
if not exist backend\.venv (echo Run setup.bat first. & goto :fail)
if not exist frontend\node_modules (echo Run setup.bat first. & goto :fail)

netstat -ano | findstr /R /C:":%JOBFINDER_PORT% .*LISTENING" >nul && (echo JobFinder already seems to be running ^(port %JOBFINDER_PORT% in use^). Opening it. & start "" http://localhost:%JOBFINDER_UI_PORT% & exit /b 0)
netstat -ano | findstr /R /C:":%JOBFINDER_UI_PORT% .*LISTENING" >nul && (echo Port %JOBFINDER_UI_PORT% is in use by another program. Run stop.bat or close it first. & goto :fail)

start "JobFinder" /min "%~dp0scripts\run-servers.cmd"

REM Wait until the frontend answers (max ~60 s on a first start), then open it.
powershell -NoProfile -Command "for($i=0;$i -lt 120;$i++){ try { Invoke-WebRequest 'http://localhost:%JOBFINDER_UI_PORT%' -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep -Milliseconds 500 } }"
if not "%JOBFINDER_NO_BROWSER%"=="1" start "" http://localhost:%JOBFINDER_UI_PORT%
exit /b 0

:fail
if not "%JOBFINDER_NO_PAUSE%"=="1" pause
exit /b 1
