@echo off
echo Installing Creative Workout Bot autostart...

schtasks /create ^
  /tn "CreativeWorkoutBot" ^
  /tr "wscript.exe \"E:\projects\creative_bot\run_hidden.vbs\"" ^
  /sc onlogon ^
  /rl highest ^
  /f

echo Done! Bot will start automatically on next login.
echo To remove: schtasks /delete /tn "CreativeWorkoutBot" /f
pause
