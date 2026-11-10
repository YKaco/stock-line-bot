@echo off
chcp 65001 > nul
echo ====================================================
echo   GitHubへの全ファイル一発送信（push）ツール
echo ====================================================
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" sync_github.py
echo.
pause
