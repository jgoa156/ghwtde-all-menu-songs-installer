@echo off
rem Builds dist\MenuMusicCollection.exe (installs PyInstaller with pip if needed).
cd /d "%~dp0"
python build.py
