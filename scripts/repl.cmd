@echo off
rem Opens the SWI-Prolog prompt with an example loaded.
rem Works from cmd, PowerShell 5.1, PowerShell 7 and Git Bash.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0repl.ps1" %*
