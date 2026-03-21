@echo off
title Abdul AI CCTV System
echo Starting Abdul AI CCTV System...
cd /d "C:\Users\Administrator\Desktop\note\test"

:: Install requirements just in case (optional, but good for first run)
echo Checking dependencies...
pip install -r requirements.txt --quiet

echo Running Streamlit app...
streamlit run app.py

:: If the program crashes, the window will stay open for user to see errors
echo ERROR: Program stopped unexpectedly.
pause
