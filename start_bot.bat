@echo off
title University Confession Bot
color 0A

echo.
echo ===============================================
echo    University Confession Bot Launcher
echo ===============================================
echo.

cd /d "%~dp0"

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python from https://python.org
    echo.
    pause
    exit /b 1
)

echo Python found! Starting bot...
echo.

python start_bot.py

if errorlevel 1 (
    echo.
    echo Bot exited with an error!
    pause
) else (
    echo.
    echo Bot stopped normally.
)
