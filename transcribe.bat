@echo off
::
:: Mimir - Audio Transcriber
::
:: Drag one or more audio files, or a folder of them, onto this script. Each
:: file is transcribed and the text is written beside the audio file. An
:: existing transcript is never overwritten: a numbered suffix is added.
::
:: Everything it needs is checked and installed by setup.bat, which runs
:: quietly before each transcription. See README.txt.
::
setlocal enabledelayedexpansion

title Mimir - Audio Transcriber

set "SCRIPT_DIR=%~dp0"
set "TOOLS_DIR=%~dp0tools"
if exist "%TOOLS_DIR%\ffmpeg.exe" set "PATH=%TOOLS_DIR%;%PATH%"
if exist "%TOOLS_DIR%\ffmpeg\bin\ffmpeg.exe" set "PATH=%TOOLS_DIR%\ffmpeg\bin;%PATH%"

for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "C_ACCENT=%ESC%[96m"
set "C_FAIL=%ESC%[91m"
set "C_MUTED=%ESC%[90m"
set "C_OK=%ESC%[92m"
set "C_RESET=%ESC%[0m"
set "C_WARN=%ESC%[93m"
set "C_WHITE=%ESC%[97m"

set "AUDIO=;.flac;.m4a;.mp3;.mp4;.mpeg;.ogg;.wav;.webm;"
set "LIST_FILE=%TEMP%\mimir_queue_%RANDOM%%RANDOM%.txt"
set "PREVIEW_LIMIT=12"
set "RESULT_FILE=%TEMP%\mimir_result_%RANDOM%%RANDOM%.txt"
set "RULE=--------------------------------------------------------------------"

if not exist "%SCRIPT_DIR%setup.bat" (
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! setup.bat is missing from this folder.
    echo    !C_MUTED!Copy the whole Mimir folder, not just this file.!C_RESET!
    echo.
    pause
    goto :terminate
)

call "%SCRIPT_DIR%setup.bat" /quiet
if errorlevel 1 goto :terminate

if not exist "%SCRIPT_DIR%.env" (
    cls
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! Missing settings file.
    echo.
    echo    !C_MUTED!A file named .env must sit beside this script, holding the!C_RESET!
    echo    !C_MUTED!transcription service address and key. See README.txt.!C_RESET!
    echo.
    pause
    goto :terminate
)

set "file_count=0"
set "skipped_count=0"

:collect_arguments
if "%~1"=="" goto :arguments_collected
if exist "%~1\" (
    call :add_folder "%~1"
) else (
    if exist "%~1" call :add_file "%~1"
)
shift
goto :collect_arguments

:arguments_collected
if not !file_count!==0 goto :menu

:prompt_for_file
cls
call :draw_header
echo    !C_WARN!No audio files were dropped onto this script.!C_RESET!
echo    !C_MUTED!Drop audio files or a folder next time, or type a path below.!C_RESET!
echo.
set "manual_path="
set /p "manual_path=   Path (blank to quit): "
if not defined manual_path goto :terminate
set "manual_path=!manual_path:"=!"
if exist "!manual_path!\" (
    call :add_folder "!manual_path!"
) else (
    if exist "!manual_path!" call :add_file "!manual_path!"
)
if !file_count!==0 goto :prompt_for_file

:menu
cls
call :draw_header
call :draw_files
echo.

choice /c SMQ /n /m "   [S] Start transcribing   [M] Right-click menu   [Q] Quit: "
set "picked=!errorlevel!"
if !picked!==3 goto :terminate
if !picked!==2 (
    call "%SCRIPT_DIR%setup.bat" /menu
    goto :menu
)

if exist "%LIST_FILE%" del /q "%LIST_FILE%" >nul 2>nul
for /l %%i in (1,1,!file_count!) do >>"%LIST_FILE%" echo !input_%%i!

cls
call :draw_header
echo    !C_ACCENT!Transcribing !file_count!. This can take a few minutes.!C_RESET!
echo.

set "MIMIR_RESULT_FILE=%RESULT_FILE%"
uv run --script "%SCRIPT_DIR%audio_transcription.py" "%LIST_FILE%"

del /q "%LIST_FILE%" >nul 2>nul
echo.

choice /c ORQ /n /m "   [O] open folder   [R] transcribe again   [Q] quit: "
if errorlevel 3 goto :terminate
if errorlevel 2 goto :menu
if exist "%RESULT_FILE%" (
    for /f "usebackq delims=" %%r in ("%RESULT_FILE%") do start "" explorer.exe /select,"%%r"
)
goto :terminate

:add_file
set "candidate_extension=%~x1"
if "!AUDIO:;%~x1;=!"=="!AUDIO!" (
    set /a skipped_count+=1
    goto :eof
)
set /a file_count+=1
set "input_!file_count!=%~f1"
goto :eof

:add_folder
for %%f in ("%~1\*") do call :add_file "%%~ff"
goto :eof

:draw_files
echo    !C_WHITE!Queued: !file_count!!C_RESET!
set "shown=0"
for /l %%i in (1,1,!file_count!) do (
    if !shown! lss %PREVIEW_LIMIT% (
        set /a shown+=1
        call :draw_file_row "!input_%%i!"
    )
)
if !file_count! gtr %PREVIEW_LIMIT% (
    set /a hidden=!file_count!-%PREVIEW_LIMIT%
    echo      !C_MUTED!... and !hidden! more!C_RESET!
)
if !skipped_count! gtr 0 (
    echo.
    echo    !C_WARN!!skipped_count! ignored - not audio files.!C_RESET!
)
goto :eof

:draw_file_row
set "row_name=%~nx1"
echo      !C_MUTED!-!C_RESET! !row_name!
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR!C_RESET!  !C_MUTED!audio to text!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
echo.
goto :eof

:terminate
del /q "%LIST_FILE%" >nul 2>nul
del /q "%RESULT_FILE%" >nul 2>nul
echo !C_RESET!
endlocal
exit /b 0
