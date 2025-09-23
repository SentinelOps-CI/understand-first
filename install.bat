@echo off
REM Understand-First Installation Script for Windows
REM This script provides a one-command installation experience

setlocal enabledelayedexpansion

echo [INFO] Starting Understand-First installation...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.9+ and try again.
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [SUCCESS] Python %PYTHON_VERSION% found

REM Check if pip is installed
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip not found. Please install pip and try again.
    exit /b 1
)

REM Install from PyPI
echo [INFO] Installing from PyPI...
pip install understand-first
if %errorlevel% neq 0 (
    echo [ERROR] Installation failed.
    exit /b 1
)

echo [SUCCESS] Understand-First installed successfully!

REM Post-installation checks
echo [INFO] Running post-installation checks...

REM Check if CLI tool is available
u --help >nul 2>&1
if %errorlevel% equ 0 (
    echo [SUCCESS] CLI tool 'u' is available
) else (
    echo [WARNING] CLI tool 'u' not found in PATH
)

REM Run doctor command
echo [INFO] Running system health check...
u doctor

echo [SUCCESS] Installation completed!
echo.
echo Next steps:
echo   1. Run 'u --help' to see available commands
echo   2. Run 'u demo' to see a complete example
echo   3. Run 'u doctor' to check system health
echo   4. Visit https://github.com/sentinelops-ci/understand-first for documentation

pause
