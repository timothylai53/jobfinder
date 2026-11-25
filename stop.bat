@echo off
REM Stops JobFinder: whatever is listening on its two ports (backend 8730, frontend 5730), with child processes.
REM JOBFINDER_PORT / JOBFINDER_UI_PORT stop a copy started on other ports (checks only).
setlocal
if "%JOBFINDER_PORT%"=="" set JOBFINDER_PORT=8730
if "%JOBFINDER_UI_PORT%"=="" set JOBFINDER_UI_PORT=5730
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":%JOBFINDER_PORT% .*LISTENING" /C:":%JOBFINDER_UI_PORT% .*LISTENING"') do (
  taskkill /F /T /PID %%p >nul 2>&1 && set FOUND=1
)
if "%FOUND%"=="1" (echo JobFinder stopped.) else (echo JobFinder was not running.)
if not "%JOBFINDER_NO_PAUSE%"=="1" timeout /t 2 >nul
endlocal
