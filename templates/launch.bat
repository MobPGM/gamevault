@echo off
cd /d "C:\Users\robert.n.mitchell\OneDrive - Accenture\Documents\game-tracker"
start python app.py
timeout /t 2 /nobreak > nul
start http://localhost:5000