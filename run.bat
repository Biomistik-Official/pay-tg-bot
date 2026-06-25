@echo off
title VGS Money Telegram Bot
cd /d "%~dp0"

:: Check for .env file
if not exist .env (
    echo [ERROR] .env file not found!
    echo Please create a .env file from .env.example and configure BOT_TOKEN and OWNER_ID.
    pause
    exit /b
)

:: Check for virtual environment
if not exist venv\Scripts\python.exe (
    echo [INFO] Creating virtual environment venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b
    )
    echo [INFO] Installing requirements from requirements.txt...
    venv\Scripts\pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b
    )
)

echo [SUCCESS] Starting the bot...
venv\Scripts\python.exe -m bot.main
pause
