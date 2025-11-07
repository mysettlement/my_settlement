@echo off
cd /d "C:\Users\server\projects\my_settlement"
powershell -NoExit -ExecutionPolicy Bypass -File "sync_git.ps1"