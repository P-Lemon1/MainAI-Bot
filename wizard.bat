@echo off
cd /d "%~dp0"
python wizard.py
if errorlevel 1 pause
