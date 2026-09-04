@echo off
::
:: Mimir - Test Runner
::
:: Runs the Python and batch-script test suite. uv fetches the test
:: dependencies into a throwaway environment, so nothing is installed
:: into the system Python. Any arguments are passed through to pytest,
:: for example: test.bat -v -k settings
::
setlocal enabledelayedexpansion

title Mimir - Tests

set "test_exit_code=1"

where uv >nul 2>nul
if errorlevel 1 (
    echo.
    echo    [ERROR] uv was not found. Run setup.bat first.
    echo.
    pause
    goto :terminate
)

uv run --no-project --with openai --with pytest --with python-docx --with python-dotenv --with typing_extensions python -m pytest %*
set "test_exit_code=!errorlevel!"

echo.
if !test_exit_code!==0 (
    echo    [ OK ] Every test passed.
) else (
    echo    [FAIL] Some tests failed. Scroll up for the details.
)
echo.

:terminate
endlocal & exit /b %test_exit_code%
