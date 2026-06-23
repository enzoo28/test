@echo on 
>nul 2>&1 net session || (
    echo This script needs administrator privileges.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)

set "HOSTS_PS=%TEMP%\dc_toggle_hosts.ps1"

REM Write PowerShell script to temp file
REM Use only ASCII in echo lines -- no Unicode chars
(
echo # Detect LAN IP via default route
echo $ip = $null
echo try {
echo     $route = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop ^| Sort-Object RouteMetric ^| Select-Object -First 1
echo     if ($route^) {
echo         $iface = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
echo         if ($iface^) { $ip = $iface.IPAddress }
echo     }
echo } catch { Write-Host "Route detection failed, using fallback..." -ForegroundColor Yellow }
echo # Fallback: first non-loopback, non-well-known IPv4 address
echo if (-not $ip^) {
echo     $ip = ^(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object {
echo         $_.IPAddress -ne '127.0.0.1' -and $_.SuffixOrigin -ne 'WellKnown'
echo     } ^| Select-Object -First 1^).IPAddress
echo }
echo if (-not $ip^) { $ip = '127.0.0.1' }
echo Write-Host ""
echo Write-Host "Detected LAN IP: $ip" -ForegroundColor Cyan
echo Write-Host ""
echo # Hosts entries needed
echo $entries = @(
echo     "$ip demoapi.cqg.com"
echo     "$ip api.cqg.com"
echo     "$ip depth-it.historical.deepcharts.com"
echo     "$ip data-b.historical.deepcharts.com"
echo ^)
echo $hostsPath = Join-Path $env:SYSTEMROOT 'System32\drivers\etc\hosts'
echo $lines = @(Get-Content $hostsPath -Encoding ASCII^)
echo $added = 0; $removed = 0
echo foreach ($e in $entries^) {
echo     if ($lines -contains $e^) {
echo         $lines = @($lines ^| Where-Object { $_ -ne $e }^)
echo         Write-Host "  [REMOVED] $e" -ForegroundColor Yellow
echo         $removed++
echo     } else {
echo         $lines += $e
echo         Write-Host "  [ADDED]   $e" -ForegroundColor Green
echo         $added++
echo     }
echo }
echo $lines ^| Out-File $hostsPath -Encoding ascii -Force
echo Write-Host ""
echo Write-Host "Done: $added added, $removed removed." -ForegroundColor Cyan
echo # Show current hosts state
echo Write-Host ""
echo Write-Host "Current hosts file entries:" -ForegroundColor DarkGray
echo Get-Content $hostsPath -Encoding ASCII ^| Where-Object { $_ -match 'cqg\.com|deepcharts\.com' } ^| ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
) > "%HOSTS_PS%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%HOSTS_PS%"
del "%HOSTS_PS%" 2>nul

if %errorlevel% equ 0 (
    echo.
) else (
    echo [!] PowerShell script failed.
)
pause
