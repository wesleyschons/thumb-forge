@echo off
echo ========================================
echo  ThumbForge — Iniciando ComfyUI Server
echo ========================================
cd D:\Dev\ThumbForge\comfyui
call .\venv\Scripts\activate
python main.py --listen 0.0.0.0 --port 8188 --lowvram --preview-method auto
pause
