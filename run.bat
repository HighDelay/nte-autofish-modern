@echo off
cd /d "%~dp0"

:: Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Check for compiled exe first (in dist/ or current dir)
if exist "dist\NTE-AutoFish-Modern.exe" (
    echo Starting NTE-AutoFish-Modern.exe...
    start "" "dist\NTE-AutoFish-Modern.exe"
    exit /b
)

if exist "NTE-AutoFish-Modern.exe" (
    echo Starting NTE-AutoFish-Modern.exe...
    start "" "NTE-AutoFish-Modern.exe"
    exit /b
)

:: Fall back to Python
echo No exe found, running with Python...
python main.py
pause
