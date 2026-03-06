@echo off
REM start.bat — Activate venv, install deps, and launch the Streamlit app

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt --quiet --only-binary :all: 2>nul
if errorlevel 1 (
    echo Binary-only install had issues, retrying with source builds allowed...
    pip install -r requirements.txt --quiet
)

echo Starting Streamlit app...
python -m streamlit run app.py
