@echo off
>nul 2>&1 net session || (
    echo This script needs administrator privileges.
    echo Right-click and select "Run as administrator".
    pause
    exit /b 1
)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0toggle-proxy-hosts.ps1"
pause
