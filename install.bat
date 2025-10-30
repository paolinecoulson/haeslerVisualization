@echo off
REM -----------------------------
REM Configuration
REM -----------------------------
SET REPO_URL=https://github.com/paolinecoulson/haeslerVisualization.git
SET APP_FOLDER=%USERPROFILE%\haeslerVisualization
SET DLL_URL=https://github.com/....  #a modifier
SET DLL_NAME=neurolayer.dll

REM -----------------------------
REM 0. Install uv if not already installed
REM -----------------------------
where uv >nul 2>nul
IF %ERRORLEVEL% NEQ 0 (
    echo uv not found. Installing uv...
    powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
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
    echo Repo already exists, skipping clone.
)

REM -----------------------------
REM 2. Change directory to app
REM -----------------------------
cd /d "%APP_FOLDER%"

REM -----------------------------
REM 3. Sync uv environment
REM -----------------------------
echo Syncing uv environment...
uv sync

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

echo Done!
pause
