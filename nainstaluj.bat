@echo off
setlocal

set "PLUGIN_DIR=%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\terasy_eval"
set "SOURCE=%~dp0terasy_eval"

if not exist "%PLUGIN_DIR%" mkdir "%PLUGIN_DIR%"

xcopy "%SOURCE%\*" "%PLUGIN_DIR%\" /E /I /Y

echo.
echo Instalacia pluginu dokoncena / Plugin installation complete.
echo Restartujte QGIS / Restart QGIS.
pause
