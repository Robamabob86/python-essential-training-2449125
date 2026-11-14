@echo off
REM One-time setup: creates a private Python environment and installs everything.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install Python 3.11+ from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup done! Now open .env in Notepad and paste your Anthropic API key.
pause
