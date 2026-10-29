@echo off
setlocal
title THOX external SSD - read-only inventory
echo THOX external SSD provisioning
echo This launcher runs read-only inventory. It never writes an SSD.
echo Use a 64-bit Windows PowerShell console as Administrator for complete inventory.
echo If your execution policy blocks the script, consult your administrator.
echo This launcher does not bypass or change execution policy.
echo.
set "THOX_SSD_PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if exist "%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe" set "THOX_SSD_PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
"%THOX_SSD_PS%" -NoLogo -NoProfile -File "%~dp0thox-external-ssd.ps1" inventory
echo.
echo Read README.md for publisher hash verification, target planning and typed confirmation.
echo The write command is a dry run unless -Apply is supplied and its exact phrase is typed.
pause
endlocal
