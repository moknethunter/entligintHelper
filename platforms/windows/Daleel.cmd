@echo off
setlocal
set "DALEEL_SOURCE=%~f1"
set "DALEEL_LABEL=%~nx1"
cd /d "%~dp0"
set "DALEEL_ROOT=%~dp0"
if not exist "%DALEEL_ROOT%python\desk.py" set "DALEEL_ROOT=%~dp0..\..\"
set "DALEEL_STATE=%LOCALAPPDATA%\Daleel"
if not exist "%DALEEL_STATE%" mkdir "%DALEEL_STATE%"
if errorlevel 1 goto failed
where py >nul 2>nul
if not errorlevel 1 (
    set "DALEEL_PYTHON=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto missing_python
    set "DALEEL_PYTHON=python"
)
%DALEEL_PYTHON% -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 goto missing_python
if "%~1"=="" (
    %DALEEL_PYTHON% -B "%DALEEL_ROOT%python\desk.py" --demo --open-browser --workspace "%DALEEL_STATE%\demo.db"
) else (
    %DALEEL_PYTHON% -B "%DALEEL_ROOT%python\desk.py" --database "%DALEEL_SOURCE%" --source-label "%DALEEL_LABEL%" --approved --open-browser --workspace "%DALEEL_STATE%\work.db"
)
if errorlevel 1 goto failed
exit /b 0

:missing_python
echo Install Python 3.10 or later for Windows and reopen Daleel.cmd.
pause
exit /b 1

:failed
echo Daleel could not start. See the message above.
pause
exit /b 1
