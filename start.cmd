@echo off
rem Starts the API and the dashboard. Runs start.ps1 without changing the
rem machine's PowerShell execution policy (the bypass applies to this run only).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
