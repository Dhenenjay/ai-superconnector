@echo off
REM Simple batch file to start the backend server in a new window
REM Double-click this file or run from command prompt

echo Starting AI Superconnector Backend in new window...
powershell -ExecutionPolicy Bypass -File "run_backend.ps1"
echo Backend server started in new window!
