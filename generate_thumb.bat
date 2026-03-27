@echo off
echo ========================================
echo  ThumbForge — Gerador de Thumbnails
echo ========================================
cd D:\Dev\ThumbForge\pipeline
call .\venv\Scripts\activate
python thumbforge.py %*
pause
