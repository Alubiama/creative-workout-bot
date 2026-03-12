@echo off
cd /d E:\projects\creative_bot
echo Waiting for network...
timeout /t 15 /nobreak >nul
:loop
.venv\Scripts\python.exe bot.py
echo Bot crashed, restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
