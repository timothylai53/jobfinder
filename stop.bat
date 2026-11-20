@echo off
REM Stops JobFinder: whatever is listening on its two ports (backend 8730, frontend 5730), with child processes.
setlocal
set FOUND=0
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /R /C:":8730 .*LISTENING" /C:":5730 .*LISTENING"') do (
  taskkill /F /T /PID %%p >nul 2>&1 && set FOUND=1
)
if "%FOUND%"=="1" (echo JobFinder stopped.) else (echo JobFinder was not running.)
if not "%JOBFINDER_NO_PAUSE%"=="1" timeout /t 2 >nul
endlocal
