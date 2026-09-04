@echo off
::
:: Mimir - Update check
::
:: Called by transcribe.bat, search.bat, and setup.bat before they draw their
:: first screen. It sets three variables in the caller: update_available (0 or
:: 1), installed_version, and latest_version. It never writes to the Mimir
:: folder and never changes an exit code.
::
:: GitHub is asked for the latest release tag at most once a day. The answer is
:: kept in %LOCALAPPDATA%\Mimir\update_check.txt, so a run is not held up by
:: the network. A check that fails or times out leaves that file stamped and
:: empty: no banner is shown, and it is not tried again until tomorrow.
::
:: update.bat writes the tag it installed into the same file, so the banner
:: goes away the moment an update finishes. A folder replaced by hand can
:: still show a stale banner until the next daily check.
::

set "update_available=0"
set "installed_version="
set "latest_version="

set "CHECK_DIR=%LOCALAPPDATA%\Mimir"
set "CHECK_FILE=%LOCALAPPDATA%\Mimir\update_check.txt"
set "CHECK_REPO=stratusadv/Mimir"
set "CHECK_VERSION_FILE=%~dp0version.txt"

if not exist "%CHECK_VERSION_FILE%" goto :eof

for /f "usebackq tokens=* delims= " %%v in ("%CHECK_VERSION_FILE%") do (
    if not "%%v"=="" set "installed_version=%%v"
)

if not defined installed_version goto :eof
if not defined LOCALAPPDATA goto :eof

if not exist "%CHECK_DIR%" mkdir "%CHECK_DIR%" >nul 2>nul
if not exist "%CHECK_DIR%" goto :eof

if not exist "%CHECK_FILE%" call :refresh_check
if exist "%CHECK_FILE%" call :expire_check
if not exist "%CHECK_FILE%" goto :eof

for /f "usebackq tokens=* delims= " %%v in ("%CHECK_FILE%") do (
    if not "%%v"=="" set "latest_version=%%v"
)

if not defined latest_version goto :eof
if /i "%installed_version%"=="%latest_version%" goto :eof

call :version_value "%installed_version%" installed_value
call :version_value "%latest_version%" latest_value

if %latest_value% gtr %installed_value% set "update_available=1"

set "installed_value="
set "latest_value="
goto :eof

:: Turns a tag such as v0.3.1 into one number, so a release that is only
:: different is not mistaken for a release that is newer. A folder can hold a
:: build ahead of the published release, and that must not be told to update.
:version_value
set "version_text=%~1"
if /i "%version_text:~0,1%"=="v" set "version_text=%version_text:~1%"

set "version_major=0"
set "version_minor=0"
set "version_patch=0"

for /f "tokens=1-3 delims=." %%a in ("%version_text%") do (
    set "version_major=%%a"
    set "version_minor=%%b"
    set "version_patch=%%c"
)

if not defined version_minor set "version_minor=0"
if not defined version_patch set "version_patch=0"

set /a "%~2=version_major * 1000000 + version_minor * 1000 + version_patch" >nul 2>nul

set "version_major="
set "version_minor="
set "version_patch="
set "version_text="
goto :eof

:: Asks GitHub for the latest release tag and stamps the cache file with it.
:: The redirection creates the file even when the request fails, which is what
:: holds the next check off until tomorrow.
:refresh_check
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; try { (Invoke-RestMethod -UseBasicParsing -TimeoutSec 5 -Uri 'https://api.github.com/repos/%CHECK_REPO%/releases/latest' -Headers @{ 'User-Agent' = 'Mimir-Update' }).tag_name } catch { }" > "%CHECK_FILE%" 2>nul
goto :eof

:: Refreshes the cache file when it was last written yesterday or earlier.
:: forfiles finds nothing, and so reports failure, while the file is from today.
:expire_check
forfiles /p "%CHECK_DIR%" /m "update_check.txt" /d -1 >nul 2>nul
if errorlevel 1 goto :eof
call :refresh_check
goto :eof
