@echo off
setlocal

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..\\..") do set REPO_ROOT=%%~fI
set ADB=C:\platform-tools\adb.exe

wsl.exe --cd "%REPO_ROOT%" bash -lc "./scripts/stop_dev.sh"

if exist "%ADB%" (
  "%ADB%" forward --remove tcp:8554
  "%ADB%" forward --remove tcp:2222
)

netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8554 >nul 2>&1
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=2222 >nul 2>&1

endlocal
