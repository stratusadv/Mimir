@echo off
::
:: Mimir Update
::
:: Fetches the latest published release of Mimir from GitHub and lays it over
:: this folder. Your settings file (app\.env), your log, and anything you put
:: in app\tools are left exactly as they are.
::
:: Double-click it. It shows the installed version and the latest one, and asks
:: before it changes anything.
::
:: "update.bat /force" installs the latest release again even when the version
:: already matches, for repairing a folder with missing or damaged files.
::
:: The copying is done by a staged copy of this file in the temp folder, so
:: update.bat can replace itself safely. That copy is started as "/apply".
::
:: Exit code 0 means the folder is on the latest release. Anything else means
:: it is not.
::
setlocal enabledelayedexpansion

title Mimir Update

set "SCRIPT_DIR=%~dp0"
set "REPO=stratusadv/Mimir"
set "VERSION_FILE=%~dp0app\version.txt"

for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "C_ACCENT=%ESC%[96m"
set "C_FAIL=%ESC%[91m"
set "C_MUTED=%ESC%[90m"
set "C_OK=%ESC%[92m"
set "C_RESET=%ESC%[0m"
set "C_WARN=%ESC%[93m"
set "C_WHITE=%ESC%[97m"

set "RULE=--------------------------------------------------------------------"

if /i "%~1"=="/apply" goto :apply

set "exit_code=0"
set "force_mode=0"
if /i "%~1"=="/force" set "force_mode=1"

for /d %%d in ("%TEMP%\mimir-update-*") do rd /s /q "%%d" >nul 2>nul

cls
call :draw_header

if not exist "%SCRIPT_DIR%setup.bat" (
    echo    !C_FAIL![FAIL]!C_RESET! setup.bat is missing from the Mimir folder.
    echo    !C_MUTED!Only part of Mimir was copied here, so there is nothing to!C_RESET!
    echo    !C_MUTED!update. Copy the whole folder, or download Mimir again.!C_RESET!
    echo.
    pause
    exit /b 1
)

call :read_local_version
call :read_latest_version
if errorlevel 1 (
    echo    !C_FAIL![FAIL]!C_RESET! Could not reach GitHub to ask what the latest version is.
    echo    !C_MUTED!Check this computer can reach the internet, then try again.!C_RESET!
    echo    !C_MUTED!You can always download Mimir by hand from!C_RESET!
    echo    !C_MUTED!https://github.com/%REPO%/releases/latest!C_RESET!
    echo.
    pause
    exit /b 1
)

echo      !C_MUTED!Installed!C_RESET!  !C_WHITE!!local_version!!C_RESET!
echo      !C_MUTED!Latest!C_RESET!     !C_WHITE!!latest_version!!C_RESET!
echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo.

if /i "!local_version!"=="!latest_version!" if !force_mode!==0 (
    echo    !C_OK![ OK ]!C_RESET! Mimir is already up to date.
    echo.
    echo    !C_MUTED!Run "update.bat /force" if you want this version installed!C_RESET!
    echo    !C_MUTED!again anyway, to repair missing or damaged files.!C_RESET!
    echo.
    pause
    exit /b 0
)

if !force_mode!==1 (
    echo    !C_WHITE!Install !latest_version! over this folder again?!C_RESET!
) else (
    echo    !C_WHITE!Update Mimir to !latest_version!?!C_RESET!
)
echo.
echo    !C_MUTED!Kept as they are: your settings file (app\.env), mimir.log, and!C_RESET!
echo    !C_MUTED!anything you put in app\tools. Everything else is replaced with!C_RESET!
echo    !C_MUTED!the released copy, so changes you made to those files are lost.!C_RESET!
echo.
echo    !C_MUTED![Y] downloads !latest_version! and installs it here.!C_RESET!
echo    !C_MUTED![N] closes this window and changes nothing.!C_RESET!
echo.

choice /c YN /n /m "   [Y] Update   [N] Quit: "
if errorlevel 2 exit /b 0

set "STAGE=%TEMP%\mimir-update-%RANDOM%%RANDOM%"
mkdir "%STAGE%" >nul 2>nul
if not exist "%STAGE%" (
    echo.
    echo    !C_FAIL![FAIL]!C_RESET! Could not create a temporary folder to download into.
    echo.
    pause
    exit /b 1
)

echo.
echo    !C_ACCENT!Downloading !latest_version! ...!C_RESET!
echo.

call :download_release
if errorlevel 1 (
    echo    !C_FAIL![FAIL]!C_RESET! The download did not finish.
    echo    !C_MUTED!Check this computer can reach the internet, then try again.!C_RESET!
    echo.
    rd /s /q "%STAGE%" >nul 2>nul
    pause
    exit /b 1
)

set "source_dir="
for /d %%d in ("%STAGE%\extract\*") do set "source_dir=%%d"

if not defined source_dir goto :bad_download
if not exist "!source_dir!\setup.bat" goto :bad_download
if not exist "!source_dir!\app\transcribe.bat" goto :bad_download

copy /y "%~f0" "%STAGE%\update.bat" >nul 2>nul
if not exist "%STAGE%\update.bat" (
    echo    !C_FAIL![FAIL]!C_RESET! Could not prepare the update.
    echo.
    rd /s /q "%STAGE%" >nul 2>nul
    pause
    exit /b 1
)

echo    !C_OK![ OK ]!C_RESET! Downloaded. Installing in a new window ...
echo.
echo    !C_MUTED!This window closes now so its own files can be replaced.!C_RESET!
echo.

start "Mimir Update" cmd /c ""%STAGE%\update.bat" /apply "%SCRIPT_DIR:~0,-1%" "!source_dir!" "!latest_version!""
exit /b 0

:bad_download
echo    !C_FAIL![FAIL]!C_RESET! What was downloaded does not look like Mimir.
echo    !C_MUTED!Nothing has been changed. Try again, or download Mimir by hand!C_RESET!
echo    !C_MUTED!from https://github.com/%REPO%/releases/latest!C_RESET!
echo.
rd /s /q "%STAGE%" >nul 2>nul
pause
exit /b 1

::
:: Reads the version recorded in app\version.txt. Folders installed before
:: update.bat existed have no such file, and are reported as unknown.
::
:read_local_version
set "local_version=not recorded"
if not exist "%VERSION_FILE%" goto :eof
for /f "usebackq tokens=* delims= " %%v in ("%VERSION_FILE%") do (
    if not "%%v"=="" set "local_version=%%v"
)
goto :eof

::
:: Asks GitHub for the tag of the newest published release.
::
:read_latest_version
set "latest_version="
for /f "usebackq delims=" %%v in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/%REPO%/releases/latest' -Headers @{ 'User-Agent' = 'Mimir-Update' }).tag_name } catch { exit 1 }" 2^>nul`) do set "latest_version=%%v"
if not defined latest_version exit /b 1
exit /b 0

::
:: Downloads the release source zip and unpacks it into the staging folder.
::
:download_release
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/%REPO%/archive/refs/tags/!latest_version!.zip' -OutFile '%STAGE%\mimir.zip'; Expand-Archive -LiteralPath '%STAGE%\mimir.zip' -DestinationPath '%STAGE%\extract' -Force } catch { exit 1 }"
if errorlevel 1 exit /b 1
if not exist "%STAGE%\extract" exit /b 1
exit /b 0

::
:: The staged half of the update, running from the temp folder so that every
:: file in the Mimir folder, this one included, can be replaced.
::
:apply
set "install_dir=%~2"
set "source_dir=%~3"
set "new_version=%~4"

cls
call :draw_header
echo    !C_ACCENT!Installing !new_version! ...!C_RESET!
echo.

timeout /t 2 /nobreak >nul 2>nul

robocopy "!source_dir!" "!install_dir!" /e /r:2 /w:1 /nfl /ndl /njh /njs /np >nul 2>nul
if errorlevel 8 (
    echo    !C_FAIL![FAIL]!C_RESET! Some files could not be replaced.
    echo    !C_MUTED!Close any Mimir window, and any program holding a file open in!C_RESET!
    echo    !C_MUTED!that folder, then run update.bat again.!C_RESET!
    echo.
    pause
    exit /b 1
)

> "!install_dir!\app\version.txt" echo !new_version!

:: Stamps the update check with what was just installed, so the banner
:: transcribe.bat and search.bat draw goes away straight away.
if defined LOCALAPPDATA (
    if not exist "%LOCALAPPDATA%\Mimir" mkdir "%LOCALAPPDATA%\Mimir" >nul 2>nul
    > "%LOCALAPPDATA%\Mimir\update_check.txt" echo !new_version!
)

echo    !C_OK![ OK ]!C_RESET! Files updated.
echo.
echo    !C_ACCENT!Checking the computer still has what Mimir needs ...!C_RESET!
echo.

call "!install_dir!\setup.bat" /quiet
if errorlevel 1 (
    echo.
    echo    !C_WARN!Mimir is updated, but something it needs is missing.!C_RESET!
    echo    !C_MUTED!Run setup.bat in the Mimir folder to sort it out.!C_RESET!
    echo.
    pause
    exit /b 1
)

cls
call :draw_header
echo    !C_OK![ OK ]!C_RESET! Mimir is now !C_WHITE!!new_version!!C_RESET!.
echo.
echo    !C_MUTED!Your settings file, your log, and app\tools were left alone.!C_RESET!
echo    !C_MUTED!The shortcut and right-click menu still point here.!C_RESET!
echo.
echo    !C_MUTED!!RULE!!C_RESET!
echo.
pause
exit /b 0

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR UPDATE!C_RESET!  !C_MUTED!fetching the latest release!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
echo.
goto :eof
