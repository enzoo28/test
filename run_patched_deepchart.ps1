$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$bridge = if ($env:BRIDGE_EXE) { $env:BRIDGE_EXE } else { Join-Path $root 'patched_run\bridge\VolumetricaBridge.exe' }
$bridgeDir = Split-Path -Parent $bridge
$app = if ($env:DEEPCHART_EXE) { $env:DEEPCHART_EXE } else { Join-Path $root 'patched_run\Deepchart.exe' }
$appDir = Split-Path -Parent $app

foreach ($name in @('Deepchart', 'VolumetricaBridge')) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        try { $_.CloseMainWindow() | Out-Null } catch {}
    }
}

Start-Sleep -Seconds 5
Get-Process -Name Deepchart,VolumetricaBridge -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Start-Process -FilePath $bridge -WorkingDirectory $bridgeDir -WindowStyle Hidden
Start-Sleep -Seconds 4
Start-Process -FilePath $app -WorkingDirectory $appDir

Get-Process -Name Deepchart,VolumetricaBridge -ErrorAction SilentlyContinue |
    Select-Object ProcessName, Id, StartTime, Path |
    Format-List
