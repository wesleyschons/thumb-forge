@echo off
echo ========================================
echo  ThumbForge — Setup Inicial
echo ========================================
echo.

REM Criar estrutura de diretorios
echo Criando diretorios...
mkdir D:\Dev\ThumbForge\comfyui\models\unet 2>nul
mkdir D:\Dev\ThumbForge\comfyui\models\clip 2>nul
mkdir D:\Dev\ThumbForge\comfyui\models\vae 2>nul
mkdir D:\Dev\ThumbForge\comfyui\custom_nodes 2>nul
mkdir D:\Dev\ThumbForge\assets\hosts\fernando 2>nul
mkdir D:\Dev\ThumbForge\assets\hosts\olhonocodigo 2>nul
mkdir D:\Dev\ThumbForge\assets\hosts\default 2>nul
mkdir D:\Dev\ThumbForge\assets\logos 2>nul
mkdir D:\Dev\ThumbForge\workflows 2>nul
mkdir D:\Dev\ThumbForge\output 2>nul
mkdir D:\Dev\ThumbForge\temp 2>nul
echo OK.

echo.
echo ========================================
echo  Instalando ComfyUI
echo ========================================
cd D:\Dev\ThumbForge
git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
cd comfyui
python -m venv venv
call .\venv\Scripts\activate
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

echo.
echo Instalando custom nodes...
cd custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
git clone https://github.com/city96/ComfyUI-GGUF.git
cd ..\..

echo.
echo ========================================
echo  Instalando Pipeline Python
echo ========================================
cd D:\Dev\ThumbForge\pipeline
python -m venv venv
call .\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

echo.
echo ========================================
echo  Setup completo!
echo ========================================
echo.
echo PROXIMOS PASSOS:
echo 1. Baixe os modelos (veja README ou plano de implementacao):
echo    - flux1-dev-Q5_K_S.gguf         -^> comfyui\models\unet\
echo    - t5-v1_1-xxl-encoder-Q4_K_M.gguf -^> comfyui\models\clip\
echo    - clip_l.safetensors             -^> comfyui\models\clip\
echo    - ae.safetensors                 -^> comfyui\models\vae\
echo.
echo 2. Certifique-se que o Claude Code esta instalado e autenticado:
echo    npm install -g @anthropic-ai/claude-code
echo    claude auth login
echo.
echo 3. Inicie o ComfyUI:
echo    start_comfyui.bat
echo.
echo 4. Gere uma thumb:
echo    generate_thumb.bat "Titulo do Video" --brand fernandoliberal
echo.
pause
