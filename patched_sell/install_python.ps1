param(
    [string]$Version = "3.13",
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$urls = @{
    "3.13" = "https://www.python.org/ftp/python/3.13.3/python-3.13.3-amd64.exe"
    "3.14" = "https://www.python.org/ftp/python/3.14.2/python-3.14.2-amd64.exe"
}

$exeName = "python-$Version-amd64.exe"
$downloadUrl = $urls[$Version]

if (-not $downloadUrl) {
    Write-Host "[!] Unsupported Python version: $Version"
    Write-Host "    Supported versions: 3.13, 3.14"
    exit 1
}

Write-Host "[*] Checking for Python $Version ..."

$found = $false
$check = Get-Command "python$Version" -ErrorAction SilentlyContinue
if ($check) {
    Write-Host "[+] Python $Version found: $($check.Source)"
    $found = $true
}

if (-not $found) {
    $pyCheck = py -$Version -c "import sys; print(sys.version)" 2>$null
    if ($pyCheck) {
        Write-Host "[+] Python $Version found via launcher: $pyCheck"
        $found = $true
    }
}

if ($found) {
    Write-Host "[*] No download needed."
    exit 0
}

Write-Host "[!] Python $Version not found."
Write-Host "[*] Downloading from: $downloadUrl"

$outPath = Join-Path $PSScriptRoot $exeName
try {
    $wc = New-Object System.Net.WebClient
    Write-Host "[*] Saving to: $outPath"
    $wc.DownloadFile($downloadUrl, $outPath)
    Write-Host "[+] Downloaded: $( [math]::Round((Get-Item $outPath).Length / 1MB, 1) ) MB"
} catch {
    Write-Host "[!] Download failed: $_"
    exit 1
}

if ($Install.IsPresent) {
    Write-Host "[*] Running installer (check 'Add Python to PATH' when prompted)..."
    Start-Process -Wait -FilePath $outPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
    Write-Host "[+] Installation complete."
} else {
    Write-Host ""
    Write-Host "  Run the installer manually: $outPath"
    Write-Host "  Or re-run with: .\install_python.ps1 -Install"
    Write-Host ""
}
