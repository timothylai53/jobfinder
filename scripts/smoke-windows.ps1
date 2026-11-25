# Windows install smoke test: after setup.bat and start.bat, check that JobFinder really answers, then run stop.bat
# and check both servers are gone. Used by CI (.github/workflows/ci.yml, job "windows-install") and runnable by hand:
#   powershell -ExecutionPolicy Bypass -File scripts\smoke-windows.ps1 [-ApiPort 8730] [-UiPort 5730]
# Offline: start it with JOBFINDER_FAKE_SOURCES=1 and JOBFINDER_NO_SCHEDULER=1 so nothing is fetched.
param([int]$ApiPort = 8730, [int]$UiPort = 5730, [int]$WaitSeconds = 120)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Wait-For([string]$Url) {
  for ($i = 0; $i -lt $WaitSeconds; $i++) {
    try { return Invoke-WebRequest $Url -UseBasicParsing -TimeoutSec 3 } catch { Start-Sleep -Seconds 1 }
  }
  throw "No answer from $Url after $WaitSeconds s"
}

function Listening([int]$Port) {
  return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

$api = "http://127.0.0.1:$ApiPort"
$ui = "http://localhost:$UiPort"

$health = Wait-For "$api/api/health"
if ($health.Content -notmatch '"ok"\s*:\s*true') { throw "Unexpected health answer: $($health.Content)" }
Write-Host "backend: health ok"

$profile = Invoke-RestMethod "$api/api/profile" -TimeoutSec 30
$jobs = Invoke-RestMethod "$api/api/jobs" -TimeoutSec 30
$sources = Invoke-RestMethod "$api/api/sources" -TimeoutSec 30
Write-Host "backend: profile ok, $(@($jobs).Count) jobs, $(@($sources).Count) sources"

$page = Wait-For $ui
if ($page.Content -notmatch 'id="root"') { throw 'The frontend page has no app root' }
$main = Invoke-WebRequest "$ui/src/main.tsx" -UseBasicParsing -TimeoutSec 60
if ($main.StatusCode -ne 200) { throw "The frontend code did not load ($($main.StatusCode))" }
$viaProxy = Invoke-RestMethod "$ui/api/health" -TimeoutSec 30   # the frontend reaches the backend through its proxy
if (-not $viaProxy.ok) { throw 'The frontend could not reach the backend' }
Write-Host 'frontend: page, code and API proxy ok'

$env:JOBFINDER_NO_PAUSE = '1'
& cmd /c "`"$root\stop.bat`""
for ($i = 0; $i -lt 20 -and ((Listening $ApiPort) -or (Listening $UiPort)); $i++) { Start-Sleep -Seconds 1 }
if ((Listening $ApiPort) -or (Listening $UiPort)) { throw 'stop.bat left a server running' }
Write-Host 'stop.bat: both servers stopped, ports free'
Write-Host 'Windows install smoke test passed.'
