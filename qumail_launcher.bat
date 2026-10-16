@echo off
title QuMail - Quantum Secure Email Client
color 0B
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8


echo.
echo  ============================================================
echo       ____        __  __       _ _
echo      / __ \      ^|  \/  ^|     ^(_) ^|
echo     ^| ^|  ^| ^|_   _^| \  / ^| __ _ _^| ^|
echo     ^| ^|  ^| ^| ^| ^| ^| ^|\/^| ^|/ _` ^| ^| ^|
echo     ^| ^|__^| ^| ^|_^| ^| ^|  ^| ^| (_^| ^| ^| ^|
echo      \___\_\\__,_^|_^|  ^|_^|\__,_^|_^|_^|
echo.
echo      Quantum Secure Email Client
echo  ============================================================
echo.

set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

echo  [*] Project root: %PROJECT_ROOT%
echo.

echo  [1/2] Starting Flask Backend Server...

if not exist "%PROJECT_ROOT%\backend\.venv\Scripts\python.exe" (
    echo  [!] ERROR: Python virtual environment not found at backend\.venv
    echo  [!] Please create it first:
    echo       cd backend
    echo       python -m venv .venv
    echo       .venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

start "QuMail Backend" /min cmd /c "chcp 65001 >nul 2>&1 && set PYTHONIOENCODING=utf-8 && cd /d "%PROJECT_ROOT%\backend" && .venv\Scripts\python.exe app.py"

echo  [OK] Backend server starting on http://localhost:5000
echo.

echo  [*] Waiting for backend to initialize...
timeout /t 3 /nobreak >nul

echo  [2/2] Starting Electron Frontend...

if not exist "%PROJECT_ROOT%\node_modules\electron\dist\electron.exe" (
    echo  [!] ERROR: Electron not found in node_modules.
    echo  [!] Please run: npm install
    echo.
    pause
    exit /b 1
)

start "QuMail Frontend" /d "%PROJECT_ROOT%" cmd /c "node_modules\electron\dist\electron.exe ."

echo  [OK] Electron app launching...
echo.
echo  ============================================================
echo   QuMail is now running!
echo   Backend:  http://localhost:5000
echo   Frontend: Electron window
echo  ============================================================
echo.
echo  This window will close in 5 seconds...
timeout /t 5 /nobreak >nul
exit
