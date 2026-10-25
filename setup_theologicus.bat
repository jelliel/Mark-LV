@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   THEOLOGICUS v1.0.5 - Installation
echo ========================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Running without admin - installing to user directory
    set INSTALL_DIR=%USERPROFILE%\Theologicus
) else (
    echo [INFO] Admin rights detected - installing to Program Files
    set INSTALL_DIR=%PROGRAMFILES%\Theologicus
)

:: Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Extract package
echo [1/4] Extracting package...
powershell -Command "Expand-Archive -Path '%~dp0THEOLOGICUS-v1.0.5-Package.zip' -DestinationPath '%INSTALL_DIR%' -Force"

:: Create virtual environment
echo [2/4] Setting up Python environment...
"%INSTALL_DIR%\python.exe" -m pip install --upgrade pip --quiet
"%INSTALL_DIR%\python.exe" -m pip install -r "%INSTALL_DIR%\requirements.txt" --quiet

:: Create shortcuts
echo [3/4] Creating shortcuts...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Theologicus.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\dist\THEOLOGICUS.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('$SMPROGRAMS\Theologicus\Theologicus.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\dist\THEOLOGICUS.exe'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Save()"

:: Create uninstaller
echo [4/4] Creating uninstaller...
(
echo @echo off
echo echo Uninstalling THEOLOGICUS...
echo rmdir /s /q "%INSTALL_DIR%"
echo rmdir /s /q "%APPDATA%\Theologicus"
echo del "%%USERPROFILE%%\Desktop\Theologicus.lnk" 2^>nul
echo echo THEOLOGICUS removed successfully.
echo pause
) > "%INSTALL_DIR%\uninstall.bat"

echo.
echo ========================================
echo   THEOLOGICUS v1.0.5 installed!
echo ========================================
echo Location: %INSTALL_DIR%
echo Desktop shortcut created.
echo.
pause
