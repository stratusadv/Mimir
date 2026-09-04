@echo off
::
:: Mimir - Search
::
:: Drag one or more .txt, .docx, or .md files, or a folder of them, onto
:: this script. Right-click also works: pick "Search with Mimir". Type
:: what you want to find; Mimir looks it up with AI and shows the
:: answer here. Then it asks if you want that written to a .txt file
:: beside the original. An existing search file is never overwritten:
:: a numbered suffix is added.
::
:: Everything it needs is checked and installed by setup.bat, which runs
:: quietly before each search. See README.md.
::
setlocal enabledelayedexpansion

title Mimir - Search

set "SCRIPT_DIR=%~dp0"
set "SETUP_FILE=%~dp0..\setup.bat"

for /f %%e in ('echo prompt $E ^| cmd') do set "ESC=%%e"

set "C_ACCENT=%ESC%[96m"
set "C_FAIL=%ESC%[91m"
set "C_MUTED=%ESC%[90m"
set "C_OK=%ESC%[92m"
set "C_RESET=%ESC%[0m"
set "C_WARN=%ESC%[93m"
set "C_WHITE=%ESC%[97m"

set "LIST_FILE=%TEMP%\mimir_queue_%RANDOM%%RANDOM%.txt"
set "PREVIEW_LIMIT=12"
set "RESULT_FILE=%TEMP%\mimir_result_%RANDOM%%RANDOM%.txt"
set "RULE=--------------------------------------------------------------------"
set "TEXT_EXTENSIONS=.docx .md .txt"

if not exist "%SETUP_FILE%" (
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! setup.bat is missing from the Mimir folder.
    echo    !C_MUTED!Copy the whole Mimir folder, not just this file.!C_RESET!
    echo.
    pause
    goto :terminate
)

call "%SETUP_FILE%" /quiet
if errorlevel 1 goto :terminate

set "update_available=0"
set "installed_version="
set "latest_version="
if exist "%SCRIPT_DIR%version_check.bat" call "%SCRIPT_DIR%version_check.bat"

if not exist "%SCRIPT_DIR%.env" (
    cls
    echo.
    echo    !C_FAIL![ERROR]!C_RESET! Missing settings file.
    echo.
    echo    !C_MUTED!A file named .env must sit beside this script, holding the!C_RESET!
    echo    !C_MUTED!service address and key. Copy .env.example to .env and fill!C_RESET!
    echo    !C_MUTED!it in. See README.md.!C_RESET!
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
if not !file_count!==0 goto :query_prompt

:prompt_for_file
cls
call :draw_header
echo    !C_WARN!No text files were dropped onto this script.!C_RESET!
echo    !C_MUTED!Drop .txt, .docx, or .md files or a folder next time, or type!C_RESET!
echo    !C_MUTED!a path below.!C_RESET!
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

:query_prompt
cls
call :draw_header
call :draw_files
echo.
echo    !C_MUTED!Type what you want to find, in plain language. Mimir reads!C_RESET!
echo    !C_MUTED!the file, looks that up with AI, and shows the answer here.!C_RESET!
echo    !C_MUTED!Then it asks if you want a .txt file written beside the original.!C_RESET!
echo    !C_MUTED!Leave this blank to quit. Nothing is written.!C_RESET!
echo.
set "search_query="
set /p "search_query=   Search for: "
if not defined search_query goto :terminate
set "search_query=!search_query:"=!"
if "!search_query!"=="" goto :terminate
set "MIMIR_SEARCH_QUERY=!search_query!"

if exist "%LIST_FILE%" del /q "%LIST_FILE%" >nul 2>nul
for /l %%i in (1,1,!file_count!) do >>"%LIST_FILE%" echo !input_%%i!

cls
call :draw_header
echo    !C_ACCENT!Searching !file_count!. This can take a minute.!C_RESET!
echo    !C_MUTED!Request: !search_query!!C_RESET!
echo.

set "MIMIR_RESULT_FILE=%RESULT_FILE%"
uv run --script "%SCRIPT_DIR%document_search.py" "%LIST_FILE%"

del /q "%LIST_FILE%" >nul 2>nul
echo.

call :load_results
call :draw_ai_warning

:finish_menu
if !result_count!==0 (
    echo    !C_MUTED![R] searches these files again with a different request.!C_RESET!
    echo    !C_MUTED![Q] closes this window. No .txt file was written.!C_RESET!
    echo.
    choice /c RQ /n /m "   [R] Search again   [Q] Quit: "
    if errorlevel 2 goto :terminate
    goto :query_prompt
)

echo    !C_MUTED![T] opens the .txt file that was just written.!C_RESET!
echo    !C_MUTED![O] opens the folder it was saved in.!C_RESET!
echo    !C_MUTED![R] searches these files again with a different request.!C_RESET!
echo    !C_MUTED![Q] closes this window.!C_RESET!
echo.
choice /c TORQ /n /m "   [T] Open result   [O] Open folder   [R] Search again   [Q] Quit: "
set "finish_picked=!errorlevel!"
if !finish_picked!==4 goto :terminate
if !finish_picked!==3 goto :query_prompt
if !finish_picked!==2 (
    start "" explorer.exe /select,"!result_1!"
    goto :terminate
)
call :open_transcript
goto :terminate

:load_results
set "result_count=0"
if not exist "%RESULT_FILE%" goto :eof
for /f "usebackq delims=" %%r in ("%RESULT_FILE%") do (
    set /a result_count+=1
    set "result_!result_count!=%%~fr"
)
goto :eof

:open_transcript
if !result_count!==1 (
    start "" "!result_1!"
    goto :eof
)

:open_transcript_prompt
cls
call :draw_header
echo    !C_WHITE!Files: !result_count!!C_RESET!
for /l %%i in (1,1,!result_count!) do call :draw_result_row %%i
echo.
set "pick="
set /p "pick=   Number to open (blank to go back): "
if not defined pick goto :eof
set "pick=!pick:"=!"
echo(!pick!|findstr /r "^[1-9][0-9]*$" >nul
if errorlevel 1 goto :open_transcript_retry
if !pick! gtr !result_count! goto :open_transcript_retry
call set "open_target=%%result_!pick!%%"
start "" "!open_target!"
goto :eof

:open_transcript_retry
echo.
echo    !C_WARN!Enter a number between 1 and !result_count!.!C_RESET!
timeout /t 2 /nobreak >nul
goto :open_transcript_prompt

:draw_result_row
call set "row_path=%%result_%1%%"
for %%p in ("!row_path!") do echo      !C_MUTED![%1]!C_RESET! %%~nxp
goto :eof

:add_file
set "matched=0"
for %%e in (%TEXT_EXTENSIONS%) do if /i "%~x1"=="%%e" set "matched=1"
if "!matched!"=="0" (
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
    echo    !C_WARN!!skipped_count! ignored - not .txt, .docx, or .md files.!C_RESET!
)
goto :eof

:draw_file_row
set "row_name=%~nx1"
echo      !C_MUTED!-!C_RESET! !row_name!
goto :eof

:draw_ai_warning
echo    !C_WARN!AI can make mistakes. Review the findings before you rely on them.!C_RESET!
echo.
goto :eof

:draw_header
echo.
echo    !C_ACCENT!!RULE!!C_RESET!
echo     !C_WHITE!MIMIR!C_RESET!  !C_MUTED!search a document!C_RESET!
echo    !C_ACCENT!!RULE!!C_RESET!
call :draw_update_banner
call :draw_ai_warning
goto :eof

:draw_update_banner
if not "%update_available%"=="1" goto :eof
echo    !C_WARN!Update available: !latest_version!!C_RESET! !C_MUTED!(this folder is !installed_version!)!C_RESET!
echo    !C_MUTED!Double-click update.bat in the Mimir folder to get it.!C_RESET!
echo.
goto :eof

:terminate
del /q "%LIST_FILE%" >nul 2>nul
del /q "%RESULT_FILE%" >nul 2>nul
echo !C_RESET!
endlocal
exit /b 0
