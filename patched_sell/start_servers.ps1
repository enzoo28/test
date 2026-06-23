$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Config from env vars with defaults
$volHistPort   = if ($env:VOL_HIST_PORT)       { $env:VOL_HIST_PORT }       else { 12010 }
$bridgePort    = if ($env:BRIDGE_PROXY_PORT)    { $env:BRIDGE_PROXY_PORT }   else { 443 }
$histScript    = if ($env:VOL_HIST_SCRIPT)      { $env:VOL_HIST_SCRIPT }     else { Join-Path $root 'vol_hist_server.py' }
$bridgeScript  = if ($env:BRIDGE_SCRIPT)        { $env:BRIDGE_SCRIPT }       else { Join-Path $root 'bridge_mitm_proxy.py' }
$bridgeProc    = if ($env:BRIDGE_PROCESS_NAME)  { $env:BRIDGE_PROCESS_NAME } else { 'VolumetricaBridge' }

# Hardcoded paths to patched executables
$deepchartExe  = Join-Path $root 'patched_run\Deepchart.exe'
$vbridgeExe    = Join-Path $root 'patched_run\bridge\VolumetricaBridge.exe'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[!] NOT running as Administrator - binding to port $bridgePort will likely fail."
}

#  Read bridge_config.json if present (overrides env) 
$configFile = Join-Path $root "bridge_config.json"
if (Test-Path $configFile) {
    try {
        $cfg = Get-Content $configFile -Raw | ConvertFrom-Json
        if ($cfg.data_source -eq "rithmic") {
            $env:RITHMIC_MODE = "1"
            $env:RITHMIC_USER   = $cfg.rithmic.user
            $env:RITHMIC_PASSWORD = $cfg.rithmic.password
            if ($cfg.rithmic.system) { $env:RITHMIC_SYSTEM = $cfg.rithmic.system }
            if ($cfg.rithmic.url)    { $env:RITHMIC_URL    = $cfg.rithmic.url }
            Write-Host "[*] bridge_config.json: data_source=rithmic"
        } else {
            $env:RITHMIC_MODE = ""
            Write-Host "[*] bridge_config.json: data_source=cqg"
        }
    } catch { Write-Host "[!] Could not read bridge_config.json: $_" }
} elseif ($env:RITHMIC_USER) {
    $env:RITHMIC_MODE = "1"
    Write-Host "[*] RITHMIC_MODE=1 detected (RITHMIC_USER env var set)"
}

#  If config is missing or incomplete, run setup wizard
$needsSetup = $false
if (-not (Test-Path $configFile)) {
    Write-Host "[!] bridge_config.json not found."
    $needsSetup = $true
} elseif (-not $cfg) {
    $needsSetup = $true
} elseif ($cfg.data_source -eq "rithmic" -and [string]::IsNullOrEmpty($cfg.rithmic.user)) {
    Write-Host "[!] Rithmic mode selected but username is empty."
    $needsSetup = $true
}

if ($needsSetup) {
    $setupScript = Join-Path $root "setup_config.py"
    if (Test-Path $setupScript) {
        Write-Host "[*] Launching setup wizard..."
        if ($env:PYTHON_EXE) { $py = $env:PYTHON_EXE } else { $py = 'python' }
        & $py $setupScript
        if (Test-Path $configFile) {
            try {
                $cfg = Get-Content $configFile -Raw | ConvertFrom-Json
                if ($cfg.data_source -eq "rithmic") {
                    $env:RITHMIC_MODE = "1"
                    $env:RITHMIC_USER   = $cfg.rithmic.user
                    $env:RITHMIC_PASSWORD = $cfg.rithmic.password
                    if ($cfg.rithmic.system) { $env:RITHMIC_SYSTEM = $cfg.rithmic.system }
                    if ($cfg.rithmic.url)    { $env:RITHMIC_URL    = $cfg.rithmic.url }
                } else {
                    $env:RITHMIC_MODE = ""
                }
            } catch { Write-Host "[!] Could not re-read config: $_" }
        } else {
            Write-Host "[!] No config after setup — exiting."
            Pause; exit 1
        }
    } else {
        Write-Host "[!] setup_config.py not found. Create bridge_config.json manually."
        Pause; exit 1
    }
}

# Pick Python executable — determined AFTER config sets RITHMIC_MODE
if ($env:PYTHON_EXE) {
    $pythonExe = $env:PYTHON_EXE
} elseif ($env:RITHMIC_MODE) {
    # Rithmic requires Python 3.13 (protobuf 4.x compatibility)
    $py313 = Get-Command "python3.13" -ErrorAction SilentlyContinue
    if ($py313) {
        $pythonExe = $py313.Source
    } else {
        $pyLauncher = py -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($pyLauncher) {
            $pythonExe = $pyLauncher
        } else {
            Write-Host "[!] Python 3.13 not found. Rithmic mode needs Python 3.13. Set PYTHON_EXE env var or install Python 3.13."
            $pythonExe = 'python'
        }
    }
} else {
    $pythonExe = 'python'
}

#  License check (offline, .lic file based)
Write-Host "[*] Running license check..."
$licenseResult = & $pythonExe "$root\license_check.py" 2>&1
foreach ($line in $licenseResult) { Write-Host "  $line" }
$licenseOk = $LASTEXITCODE -eq 0
if (-not $licenseOk) {
    Write-Host "[!] No valid license - launching login window..."
    $loginResult = & $pythonExe "$root\license_login.py" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[!] License activation cancelled or failed - exiting."
        Pause
        exit 1
    }
    Write-Host "[*] License activated. Continuing..."
}

#  Kill any existing processes 
Write-Host "[*] Killing existing bridge_mitm_proxy / vol_hist_server / Deepchart / VolumetricaBridge processes ..."
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" |
  Where-Object { $_.CommandLine -match "bridge_mitm_proxy|vol_hist_server" } |
  ForEach-Object {
    Write-Host "  Killing PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
foreach ($name in @('Deepchart', 'VolumetricaBridge')) {
    Get-Process -Name $name -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "  Killing $name PID $($_.Id)"
        try { $_.CloseMainWindow() | Out-Null } catch {}
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

#  Check ports 
$histPortCheck = Get-NetTCPConnection -LocalPort $volHistPort -ErrorAction SilentlyContinue
if ($histPortCheck) {
    $p = Get-Process -Id $histPortCheck.OwningProcess -ErrorAction SilentlyContinue
    Write-Host "[!] Port $volHistPort already in use by PID $($histPortCheck.OwningProcess) ($($p.ProcessName))"
}

$bridgePortCheck = Get-NetTCPConnection -LocalPort $bridgePort -ErrorAction SilentlyContinue
if ($bridgePortCheck) {
    $proc = Get-Process -Id $bridgePortCheck.OwningProcess -ErrorAction SilentlyContinue
    $svc  = Get-CimInstance Win32_Service -Filter "ProcessId = $($bridgePortCheck.OwningProcess)" -ErrorAction SilentlyContinue
    $svcName = if ($svc) { ($svc | Select-Object -First 1).Name } else { "unknown" }
    Write-Host "[!] Port $bridgePort in use by PID $($bridgePortCheck.OwningProcess) ($($proc.ProcessName) / $svcName) on $($bridgePortCheck.LocalAddress)"

    if ($svcName -eq "iphlpsvc") {
        Write-Host "[*] Attempting to stop iphlpsvc (IP Helper) to free port $bridgePort..."
        Stop-Service iphlpsvc -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } elseif ($svcName -ne 'unknown') {
        Write-Host "[*] Attempting to stop service $svcName ..."
        Stop-Service $svcName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }

    $bridgePortCheck = Get-NetTCPConnection -LocalPort $bridgePort -ErrorAction SilentlyContinue
    if ($bridgePortCheck) {
        Write-Host "[!] Could not free port $bridgePort. Try running as Administrator or run: net stop iphlpsvc"
    } else {
        Write-Host "[+] Port $bridgePort is now free."
    }
}

#  Start Volumetrica Historical Server 
Write-Host ""
Write-Host "Starting Volumetrica Historical Server (port $volHistPort)..."
$hist = Start-Process -WindowStyle Normal -PassThru -FilePath $pythonExe -ArgumentList "`"$histScript`""
Start-Sleep -Seconds 3

$histCheck = Get-NetTCPConnection -LocalPort $volHistPort -ErrorAction SilentlyContinue
$histOk = $histCheck -and $histCheck.OwningProcess -eq $hist.Id
if ($histOk) {
    Write-Host "[+] Volumetrica Historical Server running (PID $($hist.Id) on port $volHistPort)"
} elseif ($histCheck) {
    Write-Host "[!] Port $volHistPort is open but owned by PID $($histCheck.OwningProcess) (not our PID $($hist.Id))"
} else {
    Write-Host "[!] Volumetrica Historical Server did NOT bind to port $volHistPort"
}

#  Start Bridge MITM Proxy 
if ($env:RITHMIC_MODE) {
    Write-Host "[*] Skipping Bridge MITM Proxy in Rithmic mode (native Rithmic connects directly)"
    $bridgeOk = $false
} else {
    Write-Host ""
    Write-Host "Starting Bridge MITM Proxy (port $bridgePort)..."
    $bridge = Start-Process -WindowStyle Normal -PassThru -FilePath $pythonExe -ArgumentList "`"$bridgeScript`""
    Start-Sleep -Seconds 3

    $bridgeCheck = Get-NetTCPConnection -LocalPort $bridgePort -ErrorAction SilentlyContinue
    $bridgeOk = $bridgeCheck -and $bridgeCheck.OwningProcess -eq $bridge.Id
    if ($bridgeOk) {
        Write-Host "[+] Bridge MITM Proxy running (PID $($bridge.Id) on port $bridgePort)"
    } elseif ($bridgeCheck) {
        Write-Host "[!] Port $bridgePort is open but owned by PID $($bridgeCheck.OwningProcess) (not our PID $($bridge.Id))"
    } else {
        Write-Host "[!] Bridge MITM Proxy did NOT bind to port $bridgePort"
    }
}

#  Launch VolumetricaBridge 
Write-Host ""
Write-Host "Launching VolumetricaBridge..."
$vbridgeDir = Split-Path -Parent $vbridgeExe
if (Test-Path $vbridgeExe) {
    Start-Process -FilePath $vbridgeExe -WorkingDirectory $vbridgeDir -WindowStyle Hidden
    Write-Host "[+] VolumetricaBridge launched from: $vbridgeExe"
} else {
    Write-Host "[!] VolumetricaBridge.exe not found at: $vbridgeExe"
}
Start-Sleep -Seconds 4

#  Launch Deepchart 
Write-Host ""
Write-Host "Launching Deepchart..."
if (Test-Path $deepchartExe) {
    $appDir = Split-Path -Parent $deepchartExe
    Start-Process -FilePath $deepchartExe -WorkingDirectory $appDir
    Write-Host "[+] Deepchart launched from: $deepchartExe"
} else {
    Write-Host "[!] Deepchart.exe not found at: $deepchartExe"
}

#  Summary 
Write-Host ""
Write-Host "=============================="
if ($histOk) { Write-Host "  VOL HIST : RUNNING ($volHistPort)" } else { Write-Host "  VOL HIST : NOT RUNNING" }
if ($bridgeOk) { Write-Host "  BRIDGE   : RUNNING ($bridgePort)" } else { Write-Host "  BRIDGE   : NOT RUNNING" }
$dcRunning = Get-Process -Name Deepchart -ErrorAction SilentlyContinue
$vbRunning = Get-Process -Name VolumetricaBridge -ErrorAction SilentlyContinue
if ($dcRunning) { Write-Host "  DEEPCHART: RUNNING" } else { Write-Host "  DEEPCHART: NOT RUNNING" }
if ($vbRunning) { Write-Host "  VBRIDGE  : RUNNING" } else { Write-Host "  VBRIDGE  : NOT RUNNING" }
Write-Host "=============================="
Write-Host ""
if (-not $isAdmin) { Write-Host "[TIP] Run as Administrator to avoid port-binding issues." }
Write-Host ""
Write-Host "Close each server window to stop it."

