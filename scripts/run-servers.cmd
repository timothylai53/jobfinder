@echo off
REM Run by start.bat in one minimized window: the backend in the background of this window, the frontend in front.
REM Closing this window (or stop.bat) stops both. Ports and log files come from start.bat (defaults 8730 / 5730).
title JobFinder (close this window to stop)
if "%JOBFINDER_PORT%"=="" set JOBFINDER_PORT=8730
if "%JOBFINDER_UI_PORT%"=="" set JOBFINDER_UI_PORT=5730
REM The frontend sends API calls to this backend, and the backend accepts this frontend's origin.
set JOBFINDER_API=http://127.0.0.1:%JOBFINDER_PORT%
if not "%JOBFINDER_UI_PORT%"=="5730" set JOBFINDER_FRONTEND_ORIGINS=http://localhost:%JOBFINDER_UI_PORT%,http://127.0.0.1:%JOBFINDER_UI_PORT%
cd /d "%~dp0.."
if defined JOBFINDER_LOG_DIR goto :logged

start "" /b /d "%~dp0..\backend" "%~dp0..\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %JOBFINDER_PORT%
cd frontend
call npm run dev -- --port %JOBFINDER_UI_PORT% --strictPort
exit /b

:logged
start "" /b /d "%~dp0..\backend" "%~dp0..\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %JOBFINDER_PORT% > "%JOBFINDER_LOG_DIR%\backend.log" 2>&1
cd frontend
call npm run dev -- --port %JOBFINDER_UI_PORT% --strictPort > "%JOBFINDER_LOG_DIR%\frontend.log" 2>&1
