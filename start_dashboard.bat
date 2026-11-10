@echo off
chcp 65001 > nul
echo ====================================================
echo   AI株式投資アシスタント - Webダッシュボード起動中...
echo ====================================================
"%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m streamlit run app.py
pause
