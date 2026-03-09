@echo off
setlocal

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..\\..") do set REPO_ROOT=%%~fI
set ADB=C:\platform-tools\adb.exe

net session >nul 2>&1
if errorlevel 1 (
  echo [win] Elevation required. Relaunching as Administrator...
  powershell -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b 0
)

if not exist "%ADB%" (
  echo ADB not found at %ADB%
  exit /b 1
)

REM Clean stale forwards/proxies that can block ADB from binding.
"%ADB%" forward --remove tcp:8554 >nul 2>&1
"%ADB%" forward --remove tcp:2222 >nul 2>&1
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8554 >nul 2>&1
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=2222 >nul 2>&1

REM Allow inbound RTSP/SSH from WSL (portproxy listens on 0.0.0.0).
netsh advfirewall firewall add rule name="EyeGate RTSP 8554" dir=in action=allow protocol=TCP localport=8554 >nul 2>&1
netsh advfirewall firewall add rule name="EyeGate SSH 2222" dir=in action=allow protocol=TCP localport=2222 >nul 2>&1

"%ADB%" forward tcp:8554 tcp:554
"%ADB%" forward tcp:2222 tcp:22

REM Expose ADB-forwarded localhost ports to WSL via portproxy (requires admin).
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8554 connectaddress=127.0.0.1 connectport=8554 >nul 2>&1
if errorlevel 1 echo [win] WARN: portproxy for 8554 failed (run this .cmd as Administrator)
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=2222 connectaddress=127.0.0.1 connectport=2222 >nul 2>&1
if errorlevel 1 echo [win] WARN: portproxy for 2222 failed (run this .cmd as Administrator)

wsl.exe --cd "%REPO_ROOT%" bash -lc "./scripts/run_dev.sh"

endlocal
