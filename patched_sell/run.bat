@echo off
title Deepchart Launcher
cd /d "%~dp0"

:: Check admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Kill leftover processes
taskkill /f /im bridge_proxy.exe >nul 2>&1
taskkill /f /im vol_hist.exe >nul 2>&1
taskkill /f /im VolumetricaBridge.exe >nul 2>&1
taskkill /f /im Deepchart.exe >nul 2>&1

:: Add hosts entries (run toggle script once to ADD)
powershell -ExecutionPolicy Bypass -File "toggle-proxy-hosts.ps1" >nul 2>&1

:: Launch the license-protected launcher
deepchart_launcher.exe

:: Cleanup on exit
powershell -ExecutionPolicy Bypass -File "toggle-proxy-hosts.ps1" >nul 2>&1
taskkill /f /im bridge_proxy.exe >nul 2>&1
taskkill /f /im vol_hist.exe >nul 2>&1

echo.
echo Deepchart closed. Press any key to exit.
pause >nul
