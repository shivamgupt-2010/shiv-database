@echo off
setlocal
echo ========================================================
echo   SHIV DATABASE - 24/7 SERVICE HEALTH & STATUS CHECK
echo ========================================================
echo.

set "LOCAL_URL=http://127.0.0.1:8000/health"
set "CLOUD_URL=https://shiv-database.onrender.com/health"

echo 1. Checking LOCAL Service (Port 8000)...
powershell -NoProfile -Command "try { $res = Invoke-RestMethod -Uri '%LOCAL_URL%' -TimeoutSec 3; Write-Host '   [ONLINE] Local server responding: ' ($res | ConvertTo-Json -Compress) -ForegroundColor Green } catch { Write-Host '   [OFFLINE] Local server is not currently running on port 8000' -ForegroundColor Yellow }"

echo.
echo 2. Checking CLOUD Service (Render)...
powershell -NoProfile -Command "try { $res = Invoke-RestMethod -Uri '%CLOUD_URL%' -TimeoutSec 10; Write-Host '   [ONLINE] Cloud database responding: ' ($res | ConvertTo-Json -Compress) -ForegroundColor Green } catch { Write-Host '   [OFFLINE / SPINNING UP] Cloud server is asleep or warming up: ' $_.Exception.Message -ForegroundColor Yellow }"

echo.
echo 3. Checking Active Processes...
powershell -NoProfile -Command "$procs = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($procs) { foreach ($p in $procs) { $proc = Get-Process -Id $p -ErrorAction SilentlyContinue; Write-Host ('   Process listening on 8000: PID ' + $p + ' (' + $proc.ProcessName + ')') -ForegroundColor Cyan } } else { Write-Host '   No active process bound to port 8000.' -ForegroundColor Gray }"

echo.
echo Log location: %~dp0logs\shiv_database.log
echo ========================================================
echo.
pause
