@echo off
REM Run by start.bat in one minimized window: the backend in the background of this window, the frontend in front.
REM Closing this window (or stop.bat) stops both.
title JobFinder (close this window to stop)
cd /d "%~dp0.."
start "" /b /d "%~dp0..\backend" "%~dp0..\backend\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8730
cd frontend
call npm run dev
