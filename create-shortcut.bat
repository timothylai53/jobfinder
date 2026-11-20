@echo off
REM Optional: puts a "JobFinder" shortcut on your Desktop that runs start.bat (minimized). Run it once.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desk 'JobFinder.lnk'));" ^
  "$lnk.TargetPath = (Join-Path '%~dp0' 'start.bat');" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.WindowStyle = 7;" ^
  "$lnk.IconLocation = \"$env:SystemRoot\System32\shell32.dll,13\";" ^
  "$lnk.Description = 'Start JobFinder (local job search)';" ^
  "$lnk.Save(); Write-Host ('Shortcut created: ' + (Join-Path $desk 'JobFinder.lnk'))"
pause
