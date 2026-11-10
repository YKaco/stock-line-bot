@echo off
chcp 65001 > nul
echo ====================================================
echo   毎日のAI株式レポート作成 ＆ LINE送信
echo ====================================================
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" daily_job.py
pause
