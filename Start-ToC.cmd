@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0toc.ps1" start
if errorlevel 1 (
  echo.
  echo Times of Chaos could not start. Review the message above.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0toc.ps1" open
