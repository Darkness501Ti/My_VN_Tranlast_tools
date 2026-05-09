@echo off
setlocal enabledelayedexpansion

set "SUGOI_DIR=D:\game_install\501Translate\tools\sugoi"
set "SUGOI_BAT=%SUGOI_DIR%\startServer-CUDA.bat"
set "SUGOI_URL=http://localhost:14366"

echo.
echo ========================================
echo   YU-RIS VN Auto-Translator
echo ========================================
echo.

:: Check if Sugoi server is already running
curl -s -m 2 "%SUGOI_URL%" >NUL 2>NUL
if %errorlevel% EQU 0 (
    echo [OK] Sugoi translation server is running.
    goto :python_check
)

echo [..] Starting Sugoi translation server (GPU)...
start /min /D "%SUGOI_DIR%" "Sugoi Server" "%SUGOI_BAT%"
echo [..] Waiting for model to load (30-60 seconds on first start)...

:wait_loop
timeout /t 5 /nobreak >NUL
echo [..] Checking server...
curl -s -m 3 "%SUGOI_URL%" >NUL 2>NUL
if %errorlevel% NEQ 0 goto :wait_loop
echo [OK] Sugoi server is ready!

:python_check
echo.
echo [..] Checking Python deps (requests, murmurhash2, xor_cipher, deflate)...
python -c "import requests, murmurhash2, xor_cipher, deflate" >NUL 2>NUL
if %errorlevel% NEQ 0 (
    echo [..] Installing deps - please wait...
    pip install requests murmurhash2 xor-cipher deflate
    if %errorlevel% NEQ 0 (
        echo [ERROR] Failed to install Python deps.
        pause
        exit /b 1
    )
)
echo [OK] Python deps ready.

echo.
echo [..] Starting translation...
echo       Tools: yuri (vendored) + ypf-repacker.exe (fallback)
echo.
python "%~dp0yuris_translate.py" %*
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% EQU 0 (
    echo [SUCCESS] Translation complete! Check the _ENG_ver folder inside the game directory.
) else (
    echo [ERROR] Translation failed. See messages above.
)
echo.
pause
