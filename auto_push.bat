@echo off
cd /d E:\projects\creative_bot

:: Проверяем есть ли изменения
git diff --quiet && git diff --cached --quiet
if %errorlevel% == 0 (
    echo No changes to push.
    exit /b 0
)

:: Коммитим и пушим
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME=%%a:%%b

git add .
git commit -m "auto: daily sync %DATE% %TIME%"
git push origin main

echo Done: pushed to GitHub.
