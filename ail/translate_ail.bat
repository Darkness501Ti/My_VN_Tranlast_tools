@echo off
setlocal
REM ============================================================
REM  Ail Soft engine translator — one-click
REM  Place these files (translate_ail.bat, ail_translate.py,
REM  ail_lzss.py) into a game folder containing sall.snl and
REM  double-click this bat.
REM ============================================================

cd /d "%~dp0"

REM --- locate Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python not found in PATH.
    echo     Install Python 3.10+ from https://python.org and re-run.
    pause
    exit /b 1
)

echo [+] Using Python:
where python | findstr /n "." | findstr "^1:"
echo.

REM --- run translator ---
python "%~dp0ail_translate.py" %*
set RC=%ERRORLEVEL%

echo.
echo ============================================================
if "%RC%"=="0" (
    echo  Translation complete. See output above for ENG folder path.
) else (
    echo  Translation FAILED with code %RC%.
)
echo ============================================================
pause
exit /b %RC%
