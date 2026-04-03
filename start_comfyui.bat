@echo off
echo ========================================
echo  ThumbForge — Iniciando ComfyUI Server
echo ========================================
D:\Dev\ThumbForge\comfyui\venv\Scripts\python.exe D:\Dev\ThumbForge\comfyui\main.py --listen 0.0.0.0 --port 8188 --lowvram --preview-method auto
pause
