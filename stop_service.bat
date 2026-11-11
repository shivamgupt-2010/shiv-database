@echo off
setlocal
echo ========================================================
echo   STOPPING SHIV DATABASE 24/7 BACKGROUND SERVICE
echo ========================================================
echo.

powershell -NoProfile -Command "$procs = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if ($procs) { foreach ($p in $procs) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped process on port 8000 (PID: ' + $p + ')') -ForegroundColor Yellow } } else { Write-Host 'No running process detected on port 8000.' -ForegroundColor Gray }; Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -like '*watchdog_runner.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped Watchdog supervisor (PID: ' + $_.ProcessId + ')') -ForegroundColor Yellow }"

echo.
echo [DONE] Service stopped.
echo.
pause
