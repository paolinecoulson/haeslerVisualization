@echo off
REM -----------------------------
REM Configuration
REM -----------------------------
SET REPO_URL=https://github.com/paolinecoulson/haeslerVisualization.git
SET APP_FOLDER=%USERPROFILE%\haeslerVisualization
SET DLL_URL="https://github.com/paolinecoulson/NeuroLayerOEPlugin/releases/download/1.0.2/NIDAQ-windows_0.1.0-API10.zip"
SET DLL_NAME=NeuroLayerOEPlugin.dll

:: --------------------------------------------------
:: Require admin privileges
:: --------------------------------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)


REM -----------------------------
REM 0. Install uv if not already installed
REM -----------------------------
where uv >nul 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo [INFO] uv not found. Installing uv...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; irm https://astral.sh/uv/install.ps1 | iex"
    SET PATH="%USERPROFILE%\.local\bin;%PATH%"
) ELSE (
    echo uv is already installed.
)

REM -----------------------------
REM 1. Clone the web app repo if not already present
REM -----------------------------
IF NOT EXIST "%APP_FOLDER%" (
    echo Cloning web app repo...
    git clone "%REPO_URL%" "%APP_FOLDER%"
) ELSE (
    echo [INFO] Repo already exists, skipping clone.
    cd /d "%APP_FOLDER%"
    git fetch origin main
    git stash
    git checkout main
    git pull
)

REM -----------------------------
REM 2. Change directory to app
REM -----------------------------
cd /d "%APP_FOLDER%"

REM -----------------------------
REM 3. Sync uv environment
REM -----------------------------
echo Syncing uv environment...
uv sync --frozen
uv tool install . 

REM -----------------------------
REM 5. Download DLL from GitHub
REM -----------------------------
echo Downloading DLL...
powershell -Command "Invoke-WebRequest -Uri '%DLL_URL%' -OutFile '%TEMP%\%DLL_NAME%'"

REM -----------------------------
REM 6. Find Open-Ephys install folder
REM -----------------------------
echo Searching for Open-Ephys installation...
REM Default path (change if needed)
SET OE_DEFAULT=C:\Program Files\OpenEphys
IF EXIST "%OE_DEFAULT%\Plugins" (
    SET OE_PLUGIN_FOLDER=%OE_DEFAULT%\Plugins
) ELSE (
    REM If not found in default location, try user prompt
    echo Could not find default Open-Ephys folder.
    SET /P OE_PLUGIN_FOLDER=Enter Open-Ephys plugin folder path:
)

REM -----------------------------
REM 7. Copy DLL to plugin folder
REM -----------------------------
echo Copying DLL to Open-Ephys Plugins folder...
COPY /Y "%TEMP%\%DLL_NAME%" "%OE_PLUGIN_FOLDER%"

REM -----------------------------
REM 8. Create desktop shortcut for neurolayer_gui
REM -----------------------------
SET SHORTCUT_NAME=NeuroLayer GUI
SET DESKTOP_FOLDER=%USERPROFILE%\Desktop
SET SHORTCUT_PATH=%DESKTOP_FOLDER%\%SHORTCUT_NAME%.lnk

REM Path to the installed CLI script (uv tool installs it in %USERPROFILE%\.local\bin)
SET TARGET_PATH=%USERPROFILE%\.local\bin\neurolayer_gui.exe

powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%SHORTCUT_PATH%'); $Shortcut.TargetPath = '%TARGET_PATH%'; $Shortcut.WorkingDirectory = '%APP_FOLDER%'; $Shortcut.WindowStyle = 1; $Shortcut.IconLocation = '%TARGET_PATH%'; $Shortcut.Save()"

echo [INFO] Shortcut created on desktop.

echo Done!
pause
