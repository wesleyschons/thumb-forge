# ThumbForge — Plano de Implementação Completo
## Pipeline Automatizado de Geração de Thumbnails para YouTube
### Hardware: Ryzen 7 5700x + RTX 5060 8GB VRAM | Windows

---

## 1. VISÃO GERAL DA ARQUITETURA

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLAUDE CODE (Orquestrador)                  │
│  - Recebe briefing do vídeo                                     │
│  - Classifica tipo de thumb (template)                          │
│  - Gera prompts otimizados por camada                           │
│  - Orquestra o pipeline inteiro                                 │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PYTHON ORCHESTRATOR (thumbforge.py)            │
│  - Recebe JSON de camadas do Claude Code                        │
│  - Chama ComfyUI API para cada camada de imagem                 │
│  - Executa rembg para recorte de pessoas                        │
│  - Compõe camadas via Pillow                                    │
│  - Gera texto via Chrome headless (HTML→PNG)                    │
│  - Output final: 1280x720 PNG otimizado                         │
└───────────────┬─────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│              ComfyUI + FLUX.1 Dev GGUF Q5_K (LOCAL)             │
│  - Gera backgrounds, elementos visuais, cenários                │
│  - Roda em 8GB VRAM com --lowvram                               │
│  - API mode (porta 8188)                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. CONSTRAINTS DE HARDWARE E DECISÕES TÉCNICAS

### RTX 5060 — 8GB VRAM
- **Modelo escolhido:** FLUX.1 Dev GGUF Q5_K (~5.5GB VRAM)
  - Q4_K também funciona (~4.5GB VRAM) como fallback se Q5 estourar
  - NÃO usar fp16 (precisa de 24GB+) nem fp8 (precisa de 12GB+)
- **Text encoder:** T5-XXL fp8 (~4.8GB) — NÃO cabe simultaneamente com FLUX
  - Solução: usar `--lowvram` no ComfyUI que faz offload do T5 pra CPU/RAM
  - Alternativa: usar T5-XXL GGUF Q4 (~2.5GB) — cabe junto com FLUX Q5
- **VAE:** ae.safetensors (~168MB) — desprezível
- **Resolução de geração:** 1024x576 (16:9) ou 1280x720 nativo
  - 1024x576 é mais rápido e depois upscale 2x via Lanczos é suficiente para thumb
  - 1280x720 nativo funciona mas é mais lento (~40-60s vs ~20-30s)
- **Steps:** 20 steps com Euler scheduler para FLUX Dev
- **CFG:** 1.0 (FLUX funciona melhor com CFG baixo)

### RAM do Sistema
- Mínimo 16GB, ideal 32GB (o offload do T5 pra CPU usa ~5GB de RAM extra)

### Armazenamento
- Modelos ocupam ~8-10GB total no disco
- Output de cada thumb: ~500KB-2MB

---

## 3. INSTALAÇÃO — PASSO A PASSO WINDOWS

### 3.1 Pré-requisitos

```powershell
# Python 3.11+ (NÃO use 3.13, ComfyUI tem issues)
# Instalar via https://www.python.org/downloads/
# Marcar "Add to PATH" durante instalação

# Git
# Instalar via https://git-scm.com/download/win

# NVIDIA CUDA Toolkit 12.x (vem com o driver mais recente)
# Verificar: nvidia-smi

# Node.js 18+ (para Chrome headless text rendering)
# Instalar via https://nodejs.org/
```

### 3.2 Estrutura de Diretórios

```
C:\ThumbForge\
├── comfyui\                    # ComfyUI installation
│   ├── models\
│   │   ├── unet\               # FLUX GGUF model
│   │   ├── clip\               # Text encoders
│   │   └── vae\                # VAE
│   └── custom_nodes\           # ComfyUI-GGUF etc
├── pipeline\                   # Python orchestrator
│   ├── thumbforge.py           # Main orchestrator
│   ├── comfyui_client.py       # ComfyUI API client
│   ├── compositor.py           # Layer compositing (Pillow)
│   ├── text_renderer.py        # HTML→PNG text layer
│   ├── bg_remover.py           # rembg wrapper
│   ├── prompt_engine.py        # Claude API prompt generator
│   └── config.py               # Templates, brands, settings
├── templates\                  # Thumbnail template definitions
│   ├── podcast_duo.json        # 2 pessoas + fundo + texto
│   ├── solo_dramatic.json      # 1 pessoa + fundo cinematico + texto
│   ├── collage_epic.json       # Múltiplas figuras + cenário + texto
│   ├── reaction_split.json     # Split screen antes/depois
│   └── text_heavy.json         # Background + texto dominante
├── brands\                     # Brand definitions
│   ├── fernandoliberal.json
│   ├── olhonocodigo.json
│   └── default.json
├── assets\                     # Fotos recortadas dos hosts, logos
│   ├── hosts\
│   │   ├── fernando_surprised.png
│   │   ├── fernando_serious.png
│   │   └── fernando_pointing.png
│   └── logos\
├── workflows\                  # ComfyUI workflow JSONs
│   ├── generate_background.json
│   ├── generate_element.json
│   └── generate_scene.json
├── output\                     # Thumbs finais
└── temp\                       # Arquivos temporários por sessão
```

### 3.3 Instalação do ComfyUI

```powershell
cd C:\ThumbForge

# Clonar ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git comfyui
cd comfyui

# Criar venv
python -m venv venv
.\venv\Scripts\activate

# Instalar dependências (PyTorch com CUDA 12.x)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt

# Instalar ComfyUI Manager
cd custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git

# Instalar ComfyUI-GGUF (CRÍTICO para rodar FLUX quantizado)
git clone https://github.com/city96/ComfyUI-GGUF.git

cd ../..
```

### 3.4 Download dos Modelos

```powershell
# === FLUX.1 Dev GGUF Q5_K (~5.5GB) ===
# Download de: https://huggingface.co/city96/FLUX.1-dev-gguf
# Arquivo: flux1-dev-Q5_K_S.gguf
# Colocar em: C:\ThumbForge\comfyui\models\unet\

# === FLUX.1 Dev GGUF Q4_K (fallback, ~4.5GB) ===
# Arquivo: flux1-dev-Q4_K_S.gguf (opcional, para fallback de memória)

# === T5-XXL GGUF Q4 (~2.5GB, cabe na VRAM junto com FLUX) ===
# Download de: https://huggingface.co/city96/t5-v1_1-xxl-encoder-gguf
# Arquivo: t5-v1_1-xxl-encoder-Q4_K_M.gguf  
# Colocar em: C:\ThumbForge\comfyui\models\clip\

# === CLIP-L (~250MB) ===
# Download de: https://huggingface.co/comfyanonymous/flux_text_encoders
# Arquivo: clip_l.safetensors
# Colocar em: C:\ThumbForge\comfyui\models\clip\

# === VAE (~168MB) ===
# Download de: https://huggingface.co/black-forest-labs/FLUX.1-dev
# Arquivo: ae.safetensors
# Colocar em: C:\ThumbForge\comfyui\models\vae\
```

### 3.5 Instalação do Pipeline Python

```powershell
cd C:\ThumbForge\pipeline

# Criar venv separado do ComfyUI
python -m venv venv
.\venv\Scripts\activate

# Dependências do pipeline
pip install Pillow>=10.0
pip install rembg[gpu]           # Background removal com GPU
pip install onnxruntime-gpu      # Para rembg usar GPU
pip install websocket-client     # Para ComfyUI API
pip install requests             # HTTP client
pip install anthropic            # Claude API para prompt generation
pip install playwright           # Chrome headless para text rendering
pip install numpy

# Instalar browser do Playwright
playwright install chromium
```

### 3.6 Teste de Sanidade

```powershell
# Terminal 1: Iniciar ComfyUI em modo API
cd C:\ThumbForge\comfyui
.\venv\Scripts\activate
python main.py --listen 0.0.0.0 --port 8188 --lowvram

# Terminal 2: Testar conexão
cd C:\ThumbForge\pipeline
.\venv\Scripts\activate
python -c "import requests; print(requests.get('http://127.0.0.1:8188/system_stats').json())"
```

---

## 4. SISTEMA DE TEMPLATES

Cada template define a **estrutura de camadas** da thumb, independente da brand.
Template > Brand (template sempre tem prioridade).

### 4.1 Definição de Template: `podcast_duo.json`

```json
{
  "template_id": "podcast_duo",
  "name": "Podcast com 2 Pessoas",
  "description": "Duas pessoas (hosts/convidados) com fundo dramático e texto",
  "canvas": {
    "width": 1280,
    "height": 720
  },
  "layers": [
    {
      "id": "background",
      "type": "ai_generated",
      "z_index": 0,
      "generation": {
        "model": "flux_dev_q5",
        "resolution": [1024, 576],
        "upscale_to": [1280, 720],
        "steps": 20,
        "cfg": 1.0,
        "prompt_context": "epic cinematic background, dramatic lighting, {theme_atmosphere}",
        "negative_prompt": "text, watermark, logo, words, letters"
      },
      "position": { "x": 0, "y": 0 },
      "size": { "w": 1280, "h": 720 },
      "effects": [
        { "type": "brightness", "value": -20 },
        { "type": "gaussian_blur", "radius": 2 }
      ]
    },
    {
      "id": "person_left",
      "type": "cutout_photo",
      "z_index": 1,
      "source": "host_photo",
      "position": { "x": -50, "y": 50 },
      "size": { "w": 550, "h": 670 },
      "anchor": "bottom_left",
      "effects": [
        { "type": "drop_shadow", "offset": [5, 5], "blur": 15, "color": [0, 0, 0, 180] },
        { "type": "color_grade", "warmth": 10 }
      ],
      "requirements": {
        "expression": ["surprised", "serious", "pointing"],
        "facing": "right"
      }
    },
    {
      "id": "person_right",
      "type": "cutout_photo",
      "z_index": 2,
      "source": "guest_photo",
      "position": { "x": 780, "y": 50 },
      "size": { "w": 550, "h": 670 },
      "anchor": "bottom_right",
      "effects": [
        { "type": "drop_shadow", "offset": [-5, 5], "blur": 15, "color": [0, 0, 0, 180] }
      ],
      "requirements": {
        "expression": ["surprised", "shocked", "emotional"],
        "facing": "left"
      }
    },
    {
      "id": "center_element",
      "type": "ai_generated",
      "z_index": 3,
      "optional": true,
      "generation": {
        "model": "flux_dev_q5",
        "resolution": [512, 512],
        "steps": 15,
        "cfg": 1.0,
        "prompt_context": "single {visual_element} on transparent black background, centered, dramatic lighting, no text",
        "negative_prompt": "text, watermark, background, multiple objects"
      },
      "position": { "x": 440, "y": 150 },
      "size": { "w": 400, "h": 400 },
      "effects": [
        { "type": "glow", "color": "from_theme", "radius": 20, "intensity": 0.6 }
      ]
    },
    {
      "id": "text_top",
      "type": "text_rendered",
      "z_index": 10,
      "text_config": {
        "max_words": 4,
        "font_weight": 900,
        "font_family": "from_brand",
        "font_size_range": [64, 96],
        "color": "from_brand.primary_text",
        "stroke_width": 4,
        "stroke_color": "from_brand.stroke",
        "text_transform": "uppercase",
        "letter_spacing": 2
      },
      "position": { "x": 200, "y": 20 },
      "size": { "w": 880, "h": 200 },
      "alignment": "center"
    },
    {
      "id": "text_bottom",
      "type": "text_rendered",
      "z_index": 11,
      "optional": true,
      "text_config": {
        "max_words": 3,
        "font_weight": 900,
        "font_family": "from_brand",
        "font_size_range": [48, 72],
        "color": "from_brand.accent_text",
        "stroke_width": 3,
        "stroke_color": "from_brand.stroke"
      },
      "position": { "x": 200, "y": 580 },
      "size": { "w": 880, "h": 120 },
      "alignment": "center"
    },
    {
      "id": "border",
      "type": "shape",
      "z_index": 12,
      "optional": true,
      "shape": "rounded_rect_border",
      "color": "from_brand.border_color",
      "border_width": 6,
      "border_radius": 16,
      "position": { "x": 0, "y": 0 },
      "size": { "w": 1280, "h": 720 }
    }
  ],
  "safe_zones": {
    "duration_overlay": { "x": 1140, "y": 640, "w": 140, "h": 80 },
    "avoid_placing_text_here": true
  }
}
```

### 4.2 Template: `solo_dramatic.json`

```json
{
  "template_id": "solo_dramatic",
  "name": "Solo Dramático",
  "description": "Uma pessoa com fundo cinematográfico e texto impactante",
  "canvas": { "width": 1280, "height": 720 },
  "layers": [
    {
      "id": "background",
      "type": "ai_generated",
      "z_index": 0,
      "generation": {
        "model": "flux_dev_q5",
        "resolution": [1024, 576],
        "upscale_to": [1280, 720],
        "steps": 20,
        "cfg": 1.0,
        "prompt_context": "cinematic {theme_atmosphere} background, dramatic volumetric lighting, dark edges, 16:9",
        "negative_prompt": "text, watermark, person, face"
      },
      "position": { "x": 0, "y": 0 },
      "size": { "w": 1280, "h": 720 },
      "effects": [
        { "type": "vignette", "intensity": 0.4 }
      ]
    },
    {
      "id": "person_main",
      "type": "cutout_photo",
      "z_index": 1,
      "source": "host_photo",
      "position": { "x": 50, "y": 0 },
      "size": { "w": 650, "h": 720 },
      "anchor": "bottom_left",
      "effects": [
        { "type": "drop_shadow", "offset": [8, 4], "blur": 20, "color": [0, 0, 0, 200] },
        { "type": "rim_light", "color": "from_theme", "intensity": 0.3, "side": "right" }
      ]
    },
    {
      "id": "text_main",
      "type": "text_rendered",
      "z_index": 10,
      "text_config": {
        "max_words": 4,
        "font_weight": 900,
        "font_family": "from_brand",
        "font_size_range": [72, 120],
        "color": "from_brand.primary_text",
        "stroke_width": 5,
        "stroke_color": "from_brand.stroke",
        "text_transform": "uppercase"
      },
      "position": { "x": 580, "y": 100 },
      "size": { "w": 660, "h": 520 },
      "alignment": "right"
    }
  ]
}
```

### 4.3 Template: `collage_epic.json`

```json
{
  "template_id": "collage_epic",
  "name": "Colagem Épica",
  "description": "Múltiplas figuras + cenário grandioso + texto (estilo profecia/apocalíptico)",
  "canvas": { "width": 1280, "height": 720 },
  "layers": [
    {
      "id": "background",
      "type": "ai_generated",
      "z_index": 0,
      "generation": {
        "model": "flux_dev_q5",
        "resolution": [1280, 720],
        "steps": 25,
        "cfg": 1.0,
        "prompt_context": "epic wide shot {scene_description}, cinematic movie poster composition, dramatic sky, hyper detailed, 16:9"
      },
      "position": { "x": 0, "y": 0 },
      "size": { "w": 1280, "h": 720 }
    },
    {
      "id": "figure_center",
      "type": "ai_generated",
      "z_index": 1,
      "generation": {
        "model": "flux_dev_q5",
        "resolution": [512, 768],
        "steps": 20,
        "cfg": 1.0,
        "prompt_context": "{central_figure_description}, portrait, dramatic lighting, dark background"
      },
      "position": { "x": 390, "y": 0 },
      "size": { "w": 500, "h": 720 },
      "effects": [
        { "type": "blend_mode", "mode": "screen" }
      ]
    },
    {
      "id": "figure_left",
      "type": "cutout_photo_or_ai",
      "z_index": 2,
      "position": { "x": -30, "y": 100 },
      "size": { "w": 350, "h": 450 },
      "effects": [
        { "type": "desaturate", "amount": 0.5 },
        { "type": "drop_shadow" }
      ]
    },
    {
      "id": "figure_right",
      "type": "cutout_photo_or_ai",
      "z_index": 3,
      "position": { "x": 960, "y": 100 },
      "size": { "w": 350, "h": 450 },
      "effects": [
        { "type": "desaturate", "amount": 0.5 },
        { "type": "drop_shadow" }
      ]
    },
    {
      "id": "text_subtitle",
      "type": "text_rendered",
      "z_index": 10,
      "text_config": {
        "max_words": 4,
        "font_size_range": [36, 48],
        "color": "#FFFFFF",
        "font_weight": 600,
        "letter_spacing": 6,
        "text_transform": "uppercase"
      },
      "position": { "x": 200, "y": 420 },
      "size": { "w": 880, "h": 60 }
    },
    {
      "id": "text_main",
      "type": "text_rendered",
      "z_index": 11,
      "text_config": {
        "max_words": 3,
        "font_size_range": [96, 140],
        "color": "from_brand.accent_text",
        "font_weight": 900,
        "stroke_width": 5,
        "stroke_color": "#000000"
      },
      "position": { "x": 100, "y": 480 },
      "size": { "w": 1080, "h": 200 }
    }
  ]
}
```

### 4.4 Brand Definition: `fernandoliberal.json`

```json
{
  "brand_id": "fernandoliberal",
  "channel": "@fernandoliberaloficial",
  "colors": {
    "primary": "#C0392B",
    "secondary": "#F39C12",
    "accent": "#E74C3C",
    "dark": "#1A1A2E",
    "light": "#FFFFFF"
  },
  "text": {
    "primary_text": "#FFFFFF",
    "accent_text": "#FF4444",
    "stroke": "#000000",
    "highlight": "#FFD700"
  },
  "typography": {
    "primary_font": "Montserrat",
    "weights": [800, 900],
    "fallback": "Impact, Arial Black, sans-serif"
  },
  "style": {
    "border_color": "#C0392B",
    "use_border": true,
    "border_width": 6,
    "glow_color": "#FF6B35",
    "theme_moods": ["fire", "divine", "dramatic", "prophetic"]
  },
  "host_photos_dir": "C:\\ThumbForge\\assets\\hosts\\fernando"
}
```

---

## 5. PROMPT ENGINE — CLAUDE API

### 5.1 `prompt_engine.py`

Este módulo usa a API do Claude para receber o briefing do vídeo e gerar:
1. Classificação do template ideal
2. Textos da thumb (principal + secundário)
3. Prompts FLUX otimizados para cada camada AI-generated
4. Seleção de foto do host (expressão mais adequada)

```python
"""
prompt_engine.py — Gerador de prompts usando Claude API

Recebe: título do vídeo, descrição, brand_id
Retorna: JSON completo com todas as decisões da thumb
"""
import json
from anthropic import Anthropic

SYSTEM_PROMPT = """Você é um especialista em design de thumbnails virais para YouTube.
Sua tarefa é receber o briefing de um vídeo e retornar um JSON com todas as decisões
necessárias para gerar uma thumbnail de alto CTR.

REGRAS CRÍTICAS:
- Texto da thumb NUNCA repete o título do vídeo — complementa
- Máximo 3-4 palavras no texto principal
- Máximo 2-3 palavras no texto secundário (se houver)
- Prompts FLUX devem ser em inglês, detalhados, sem texto na imagem
- Sempre inclua "no text, no watermark, no letters" nos prompts de imagem
- Escolha o template que MAXIMIZA curiosity gap

TEMPLATES DISPONÍVEIS:
- podcast_duo: 2 pessoas + fundo + texto (use para podcasts, debates, entrevistas)
- solo_dramatic: 1 pessoa + fundo cinematico + texto (use para conteúdo solo, vlogs)
- collage_epic: Múltiplas figuras + cenário grandioso (use para temas épicos, profecias, geopolítica)
- reaction_split: Split screen antes/depois (use para transformações, comparações)
- text_heavy: Background + texto dominante (use quando NÃO tem foto de host)

RESPONDA APENAS COM JSON VÁLIDO, sem markdown, sem explicações."""

GENERATION_PROMPT_TEMPLATE = """
Briefing do vídeo:
- Título: {title}
- Descrição: {description}
- Brand: {brand_id}
- Fotos disponíveis do host: {available_photos}
- Templates disponíveis: {templates}

Gere o JSON de decisão da thumb com esta estrutura:
{{
  "template_id": "id do template escolhido",
  "reasoning": "1 frase explicando a escolha",
  "texts": {{
    "text_top": "TEXTO PRINCIPAL (3-4 palavras max)",
    "text_bottom": "texto secundário opcional ou null"
  }},
  "layers": {{
    "background": {{
      "flux_prompt": "prompt em inglês para FLUX gerar o background...",
      "atmosphere": "fire|divine|dark|cosmic|urban|nature"
    }},
    "center_element": {{
      "needed": true/false,
      "flux_prompt": "prompt para elemento central se needed",
      "description": "o que é o elemento"
    }},
    "person_left": {{
      "source": "nome_do_arquivo.png ou null",
      "expression_needed": "surprised|serious|pointing|angry|happy"
    }},
    "person_right": {{
      "source": "nome_do_arquivo.png ou null",
      "expression_needed": "surprised|shocked|emotional"
    }},
    "extra_figures": [
      {{
        "flux_prompt": "prompt se for figura AI-generated",
        "position": "left|center|right"
      }}
    ]
  }},
  "color_override": {{
    "use_brand_defaults": true,
    "custom_glow_color": null,
    "custom_accent": null
  }}
}}
"""

class PromptEngine:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
    
    def generate_thumb_plan(
        self,
        title: str,
        description: str,
        brand_id: str,
        available_photos: list[str],
        templates: list[str]
    ) -> dict:
        """Gera o plano completo da thumbnail via Claude API."""
        
        user_prompt = GENERATION_PROMPT_TEMPLATE.format(
            title=title,
            description=description,
            brand_id=brand_id,
            available_photos=json.dumps(available_photos),
            templates=json.dumps(templates)
        )
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        raw = response.content[0].text
        # Limpa possíveis artefatos
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        
        return json.loads(raw)
```

---

## 6. ComfyUI API CLIENT

### 6.1 `comfyui_client.py`

```python
"""
comfyui_client.py — Cliente para ComfyUI API (porta 8188)

Envia workflows, aguarda resultado, retorna path da imagem gerada.
Gerencia fila e timeout. Otimizado para 8GB VRAM.
"""
import json
import time
import uuid
import urllib.request
import urllib.parse
import websocket
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"

class ComfyUIClient:
    def __init__(self, server_url: str = COMFYUI_URL):
        self.server_url = server_url
        self.client_id = str(uuid.uuid4())
        self.ws = None
    
    def connect_ws(self):
        """Conecta ao WebSocket para monitorar progresso."""
        ws_url = f"ws://{self.server_url.split('//')[1]}/ws?clientId={self.client_id}"
        self.ws = websocket.WebSocket()
        self.ws.connect(ws_url)
    
    def queue_prompt(self, workflow: dict) -> str:
        """Envia workflow para fila e retorna prompt_id."""
        payload = json.dumps({
            "prompt": workflow,
            "client_id": self.client_id
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{self.server_url}/prompt",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        response = json.loads(urllib.request.urlopen(req).read())
        return response["prompt_id"]
    
    def wait_for_completion(self, prompt_id: str, timeout: int = 180) -> dict:
        """Aguarda conclusão via WebSocket. Retorna outputs."""
        if not self.ws:
            self.connect_ws()
        
        start = time.time()
        while time.time() - start < timeout:
            msg = self.ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("type") == "executed":
                    if data["data"].get("prompt_id") == prompt_id:
                        return data["data"]["output"]
                elif data.get("type") == "execution_error":
                    raise RuntimeError(f"ComfyUI error: {data}")
        
        raise TimeoutError(f"ComfyUI timeout after {timeout}s")
    
    def get_image(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """Baixa imagem gerada do ComfyUI."""
        params = urllib.parse.urlencode({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        })
        url = f"{self.server_url}/view?{params}"
        return urllib.request.urlopen(url).read()
    
    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 576,
        steps: int = 20,
        cfg: float = 1.0,
        seed: int = -1,
        negative_prompt: str = "text, watermark, blurry, low quality"
    ) -> bytes:
        """Gera imagem com FLUX via workflow template. Retorna bytes PNG."""
        
        if seed == -1:
            seed = int(time.time() * 1000) % (2**32)
        
        # Workflow FLUX GGUF para ComfyUI
        workflow = self._build_flux_gguf_workflow(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed
        )
        
        prompt_id = self.queue_prompt(workflow)
        output = self.wait_for_completion(prompt_id)
        
        # Extrair filename do output
        images = output.get("images", [])
        if images:
            return self.get_image(
                images[0]["filename"],
                images[0].get("subfolder", "")
            )
        
        raise RuntimeError("No images in output")
    
    def _build_flux_gguf_workflow(
        self, prompt, negative_prompt, width, height, steps, cfg, seed
    ) -> dict:
        """Constrói workflow ComfyUI para FLUX GGUF."""
        return {
            "1": {
                "class_type": "UnetLoaderGGUF",
                "inputs": {
                    "unet_name": "flux1-dev-Q5_K_S.gguf"
                }
            },
            "2": {
                "class_type": "CLIPLoaderGGUF",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                    "type": "flux"
                }
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {
                    "vae_name": "ae.safetensors"
                }
            },
            "4": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": prompt,
                    "clip": ["2", 0]
                }
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                }
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "model": ["1", 0],
                    "positive": ["4", 0],
                    "negative": ["4", 0],  # FLUX ignora negative
                    "latent_image": ["5", 0],
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0
                }
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["6", 0],
                    "vae": ["3", 0]
                }
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {
                    "images": ["7", 0],
                    "filename_prefix": "thumbforge"
                }
            }
        }
    
    def free_memory(self):
        """Libera VRAM entre gerações (CRÍTICO para 8GB)."""
        try:
            urllib.request.urlopen(
                f"{self.server_url}/free",
                data=json.dumps({"unload_models": True}).encode()
            )
            time.sleep(2)  # Aguardar liberação
        except Exception:
            pass
    
    def close(self):
        if self.ws:
            self.ws.close()
```

---

## 7. COMPOSITOR DE CAMADAS

### 7.1 `compositor.py`

```python
"""
compositor.py — Composição de camadas via Pillow

Recebe lista de camadas (imagens + configurações) e compõe a thumb final.
Suporta: blend modes, drop shadow, glow, vignette, color grading, rim light.
"""
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import numpy as np
from pathlib import Path

class ThumbCompositor:
    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.canvas = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    
    def add_layer(
        self,
        image: Image.Image,
        position: tuple[int, int] = (0, 0),
        size: tuple[int, int] | None = None,
        effects: list[dict] | None = None,
        blend_mode: str = "normal"
    ):
        """Adiciona camada ao canvas com efeitos."""
        layer = image.convert("RGBA")
        
        # Resize se necessário
        if size:
            layer = layer.resize(size, Image.LANCZOS)
        
        # Aplicar efeitos
        if effects:
            for effect in effects:
                layer = self._apply_effect(layer, effect)
        
        # Compor no canvas
        if blend_mode == "normal":
            self.canvas.paste(layer, position, layer)
        elif blend_mode == "screen":
            self._blend_screen(layer, position)
        elif blend_mode == "multiply":
            self._blend_multiply(layer, position)
    
    def _apply_effect(self, img: Image.Image, effect: dict) -> Image.Image:
        """Aplica efeito individual a uma camada."""
        etype = effect["type"]
        
        if etype == "drop_shadow":
            return self._add_drop_shadow(
                img,
                offset=effect.get("offset", (5, 5)),
                blur=effect.get("blur", 15),
                color=tuple(effect.get("color", [0, 0, 0, 180]))
            )
        
        elif etype == "glow":
            return self._add_glow(
                img,
                color=effect.get("color", "#FF6B35"),
                radius=effect.get("radius", 20),
                intensity=effect.get("intensity", 0.6)
            )
        
        elif etype == "gaussian_blur":
            return img.filter(ImageFilter.GaussianBlur(radius=effect.get("radius", 2)))
        
        elif etype == "brightness":
            enhancer = ImageEnhance.Brightness(img)
            factor = 1.0 + (effect.get("value", 0) / 100)
            return enhancer.enhance(factor)
        
        elif etype == "vignette":
            return self._add_vignette(img, effect.get("intensity", 0.4))
        
        elif etype == "desaturate":
            amount = effect.get("amount", 0.5)
            enhancer = ImageEnhance.Color(img)
            return enhancer.enhance(1.0 - amount)
        
        elif etype == "rim_light":
            return self._add_rim_light(
                img,
                color=effect.get("color", "#FF6B35"),
                intensity=effect.get("intensity", 0.3),
                side=effect.get("side", "right")
            )
        
        elif etype == "color_grade":
            warmth = effect.get("warmth", 0)
            return self._color_grade(img, warmth)
        
        return img
    
    def _add_drop_shadow(self, img, offset, blur, color):
        """Adiciona sombra projetada."""
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        shadow_layer = Image.new("RGBA", img.size, color)
        shadow.paste(shadow_layer, mask=img.split()[3])
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
        
        result_size = (
            img.size[0] + abs(offset[0]) + blur * 2,
            img.size[1] + abs(offset[1]) + blur * 2
        )
        result = Image.new("RGBA", result_size, (0, 0, 0, 0))
        result.paste(shadow, (max(offset[0], 0) + blur, max(offset[1], 0) + blur))
        result.paste(img, (max(-offset[0], 0) + blur, max(-offset[1], 0) + blur), img)
        
        return result
    
    def _add_glow(self, img, color, radius, intensity):
        """Adiciona glow ao redor do objeto."""
        if isinstance(color, str):
            color = self._hex_to_rgba(color, int(255 * intensity))
        
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        glow_layer = Image.new("RGBA", img.size, color)
        glow.paste(glow_layer, mask=img.split()[3])
        glow = glow.filter(ImageFilter.GaussianBlur(radius=radius))
        
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(glow, (0, 0))
        result.paste(img, (0, 0), img)
        return result
    
    def _add_vignette(self, img, intensity):
        """Adiciona efeito vignette."""
        w, h = img.size
        vignette = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vignette)
        
        for i in range(min(w, h) // 2):
            alpha = int(255 * intensity * (1 - i / (min(w, h) / 2)) ** 2)
            alpha = max(0, min(255, alpha))
            draw.rectangle(
                [i, i, w - i - 1, h - i - 1],
                outline=(0, 0, 0, alpha)
            )
        
        result = img.copy()
        result = Image.alpha_composite(result, vignette)
        return result
    
    def _add_rim_light(self, img, color, intensity, side):
        """Adiciona rim light lateral."""
        if isinstance(color, str):
            color = self._hex_to_rgba(color, int(255 * intensity))
        
        w, h = img.size
        rim = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        
        # Criar gradiente lateral
        arr = np.array(img)
        alpha = arr[:, :, 3]
        
        gradient = np.zeros((h, w), dtype=np.float32)
        if side == "right":
            for x in range(w):
                gradient[:, x] = (x / w) ** 2
        else:
            for x in range(w):
                gradient[:, x] = (1 - x / w) ** 2
        
        # Aplicar apenas nas bordas (onde alpha muda)
        from scipy.ndimage import sobel
        try:
            edges = sobel(alpha.astype(float))
            edges = (edges > 10).astype(float)
            edges_blurred = Image.fromarray((edges * 255).astype(np.uint8))
            edges_blurred = edges_blurred.filter(ImageFilter.GaussianBlur(radius=3))
            edges = np.array(edges_blurred).astype(float) / 255
        except ImportError:
            # Fallback sem scipy: usar gradiente simples
            edges = (alpha > 0).astype(float)
        
        rim_alpha = (gradient * edges * intensity * 255).clip(0, 255).astype(np.uint8)
        rim = Image.new("RGBA", (w, h), color[:3] + (0,))
        rim.putalpha(Image.fromarray(rim_alpha))
        
        result = Image.alpha_composite(img, rim)
        return result
    
    def _color_grade(self, img, warmth):
        """Ajuste de temperatura de cor."""
        arr = np.array(img).astype(float)
        arr[:, :, 0] = np.clip(arr[:, :, 0] + warmth, 0, 255)  # R
        arr[:, :, 2] = np.clip(arr[:, :, 2] - warmth, 0, 255)  # B
        return Image.fromarray(arr.astype(np.uint8))
    
    def _blend_screen(self, layer, position):
        """Screen blend mode."""
        # Extrair região do canvas
        region = self.canvas.crop((
            position[0], position[1],
            position[0] + layer.width,
            position[1] + layer.height
        ))
        
        arr_base = np.array(region).astype(float) / 255
        arr_layer = np.array(layer).astype(float) / 255
        
        # Ajustar tamanhos se necessário
        min_h = min(arr_base.shape[0], arr_layer.shape[0])
        min_w = min(arr_base.shape[1], arr_layer.shape[1])
        arr_base = arr_base[:min_h, :min_w]
        arr_layer = arr_layer[:min_h, :min_w]
        
        result = 1 - (1 - arr_base) * (1 - arr_layer)
        result = (result * 255).clip(0, 255).astype(np.uint8)
        
        self.canvas.paste(
            Image.fromarray(result),
            position
        )
    
    def _blend_multiply(self, layer, position):
        """Multiply blend mode."""
        region = self.canvas.crop((
            position[0], position[1],
            position[0] + layer.width,
            position[1] + layer.height
        ))
        arr_base = np.array(region).astype(float) / 255
        arr_layer = np.array(layer).astype(float) / 255
        
        min_h = min(arr_base.shape[0], arr_layer.shape[0])
        min_w = min(arr_base.shape[1], arr_layer.shape[1])
        
        result = arr_base[:min_h, :min_w] * arr_layer[:min_h, :min_w]
        result = (result * 255).clip(0, 255).astype(np.uint8)
        
        self.canvas.paste(Image.fromarray(result), position)
    
    def add_border(self, color, width, radius=0):
        """Adiciona borda ao canvas."""
        if isinstance(color, str):
            color = self._hex_to_rgba(color, 255)
        
        draw = ImageDraw.Draw(self.canvas)
        draw.rounded_rectangle(
            [0, 0, self.width - 1, self.height - 1],
            radius=radius,
            outline=color[:3],
            width=width
        )
    
    def save(self, path: str, optimize: bool = True):
        """Salva thumb final como PNG otimizado."""
        output = self.canvas.convert("RGB")  # YouTube não suporta alpha
        output.save(path, "PNG", optimize=optimize)
        return path
    
    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b, alpha)
```

---

## 8. TEXT RENDERER (HTML → PNG)

### 8.1 `text_renderer.py`

```python
"""
text_renderer.py — Renderiza texto da thumb via Chrome headless

Gera HTML com CSS styled text → screenshot via Playwright → PNG transparente.
Isso garante:
- Fontes Google Fonts perfeitas
- Stroke/outline preciso
- Sombra de texto
- Kerning e tracking profissional
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family={font_family}:wght@{font_weight}&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px;
    height: {height}px;
    background: transparent;
    display: flex;
    align-items: {vertical_align};
    justify-content: {horizontal_align};
    overflow: hidden;
  }}
  .text {{
    font-family: '{font_family}', Impact, Arial Black, sans-serif;
    font-weight: {font_weight};
    font-size: {font_size}px;
    color: {color};
    text-transform: {text_transform};
    letter-spacing: {letter_spacing}px;
    line-height: 1.1;
    text-align: {text_align};
    -webkit-text-stroke: {stroke_width}px {stroke_color};
    paint-order: stroke fill;
    text-shadow: 
      0 0 10px rgba(0,0,0,0.8),
      0 4px 8px rgba(0,0,0,0.6);
    word-wrap: break-word;
    max-width: 100%;
    padding: 10px;
  }}
  .highlight {{
    color: {highlight_color};
  }}
</style>
</head>
<body>
  <div class="text">{text_html}</div>
</body>
</html>
"""

class TextRenderer:
    def __init__(self):
        self.browser = None
        self.context = None
    
    async def init(self):
        """Inicializa browser."""
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=2  # Retina quality
        )
    
    async def render_text(
        self,
        text: str,
        width: int,
        height: int,
        font_family: str = "Montserrat",
        font_weight: int = 900,
        font_size: int = 80,
        color: str = "#FFFFFF",
        stroke_width: int = 4,
        stroke_color: str = "#000000",
        text_transform: str = "uppercase",
        letter_spacing: int = 2,
        text_align: str = "center",
        highlight_color: str = "#FF4444",
        highlight_words: list[str] | None = None,
        output_path: str = "text_layer.png"
    ) -> str:
        """Renderiza texto como PNG transparente."""
        
        if not self.browser:
            await self.init()
        
        # Processar highlight words
        text_html = text
        if highlight_words:
            for word in highlight_words:
                text_html = text_html.replace(
                    word,
                    f'<span class="highlight">{word}</span>'
                )
        
        html = HTML_TEMPLATE.format(
            font_family=font_family.replace(" ", "+"),
            font_weight=font_weight,
            width=width,
            height=height,
            font_size=font_size,
            color=color,
            stroke_width=stroke_width,
            stroke_color=stroke_color,
            text_transform=text_transform,
            letter_spacing=letter_spacing,
            text_align=text_align,
            vertical_align="center",
            horizontal_align="center",
            text_html=text_html,
            highlight_color=highlight_color
        )
        
        page = await self.context.new_page()
        await page.set_content(html)
        await page.wait_for_load_state("networkidle")
        
        # Screenshot com transparência
        await page.screenshot(
            path=output_path,
            omit_background=True,  # Fundo transparente!
            clip={"x": 0, "y": 0, "width": width, "height": height}
        )
        
        await page.close()
        return output_path
    
    async def close(self):
        if self.browser:
            await self.browser.close()


def render_text_sync(**kwargs) -> str:
    """Wrapper síncrono para o TextRenderer."""
    renderer = TextRenderer()
    result = asyncio.run(_render(renderer, **kwargs))
    return result

async def _render(renderer, **kwargs):
    await renderer.init()
    result = await renderer.render_text(**kwargs)
    await renderer.close()
    return result
```

---

## 9. BACKGROUND REMOVER

### 9.1 `bg_remover.py`

```python
"""
bg_remover.py — Remove fundo de fotos usando rembg

Otimizado para rodar na GPU quando disponível.
Nota: rembg usa ONNX Runtime, NÃO compete com VRAM do FLUX
(desde que FLUX não esteja rodando simultaneamente).
"""
from rembg import remove, new_session
from PIL import Image
from pathlib import Path

class BackgroundRemover:
    def __init__(self, model_name: str = "u2net"):
        """
        Modelos disponíveis:
        - u2net: melhor qualidade geral (170MB)
        - u2net_human_seg: otimizado para pessoas (170MB)  
        - isnet-general-use: rápido e bom (43MB)
        """
        self.session = new_session(model_name)
    
    def remove_background(
        self,
        input_path: str,
        output_path: str | None = None,
        alpha_matting: bool = True,
        foreground_threshold: int = 240,
        background_threshold: int = 10
    ) -> Image.Image:
        """Remove fundo e retorna imagem RGBA."""
        
        img = Image.open(input_path)
        
        result = remove(
            img,
            session=self.session,
            alpha_matting=alpha_matting,
            alpha_matting_foreground_threshold=foreground_threshold,
            alpha_matting_background_threshold=background_threshold
        )
        
        if output_path:
            result.save(output_path, "PNG")
        
        return result
```

---

## 10. ORQUESTRADOR PRINCIPAL

### 10.1 `thumbforge.py`

```python
"""
thumbforge.py — Orquestrador principal do ThumbForge

Fluxo:
1. Recebe briefing (título + descrição + brand)
2. Claude gera plano da thumb (template + prompts + textos)
3. Para cada camada AI: chama ComfyUI → gera imagem
4. Para cada foto: rembg remove fundo
5. Para cada texto: Chrome headless renderiza
6. Compositor monta tudo em camadas
7. Output final: 1280x720 PNG

GESTÃO DE MEMÓRIA (CRÍTICO para 8GB):
- Gera uma imagem AI por vez
- Chama free_memory() entre gerações
- rembg roda DEPOIS de todas as gerações FLUX
- Mantém apenas 1 modelo carregado por vez
"""
import json
import os
import sys
import time
import asyncio
from pathlib import Path
from PIL import Image
from io import BytesIO

from config import load_template, load_brand, TEMPLATES_DIR, BRANDS_DIR, ASSETS_DIR
from prompt_engine import PromptEngine
from comfyui_client import ComfyUIClient
from compositor import ThumbCompositor
from text_renderer import TextRenderer, render_text_sync
from bg_remover import BackgroundRemover

class ThumbForge:
    def __init__(self, anthropic_api_key: str):
        self.prompt_engine = PromptEngine(anthropic_api_key)
        self.comfyui = ComfyUIClient()
        self.bg_remover = BackgroundRemover(model_name="u2net_human_seg")
        self.text_renderer = TextRenderer()
        
        # Diretórios
        self.temp_dir = Path("C:/ThumbForge/temp")
        self.output_dir = Path("C:/ThumbForge/output")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(
        self,
        title: str,
        description: str = "",
        brand_id: str = "default",
        host_photos: list[str] | None = None,
        output_name: str | None = None
    ) -> str:
        """Pipeline completo de geração."""
        
        print(f"\n{'='*60}")
        print(f"🎬 ThumbForge — Gerando thumbnail")
        print(f"📌 Título: {title}")
        print(f"🎨 Brand: {brand_id}")
        print(f"{'='*60}\n")
        
        # === FASE 1: PLANEJAMENTO (Claude API) ===
        print("🧠 Fase 1: Gerando plano com Claude...")
        brand = load_brand(brand_id)
        available_templates = [
            f.stem for f in Path(TEMPLATES_DIR).glob("*.json")
        ]
        available_photos = host_photos or self._list_host_photos(brand)
        
        plan = self.prompt_engine.generate_thumb_plan(
            title=title,
            description=description,
            brand_id=brand_id,
            available_photos=available_photos,
            templates=available_templates
        )
        
        print(f"  ✅ Template: {plan['template_id']}")
        print(f"  ✅ Texto principal: {plan['texts']['text_top']}")
        print(f"  ✅ Texto secundário: {plan['texts'].get('text_bottom', 'nenhum')}")
        print(f"  ✅ Razão: {plan.get('reasoning', '')}")
        
        # Salvar plano para debug
        plan_path = self.temp_dir / "current_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        
        # === FASE 2: GERAÇÃO DE IMAGENS AI (ComfyUI) ===
        print("\n🎨 Fase 2: Gerando imagens com FLUX...")
        template = load_template(plan["template_id"])
        generated_layers = {}
        
        for layer in template["layers"]:
            if layer["type"] == "ai_generated":
                layer_id = layer["id"]
                layer_plan = plan["layers"].get(layer_id, {})
                
                # Skip se opcional e não necessário
                if layer.get("optional") and not layer_plan.get("needed", False):
                    print(f"  ⏭️ Camada '{layer_id}' — skip (opcional)")
                    continue
                
                prompt = layer_plan.get("flux_prompt", "")
                if not prompt:
                    prompt = layer["generation"]["prompt_context"]
                
                gen_config = layer["generation"]
                res = gen_config.get("resolution", [1024, 576])
                
                print(f"  🖼️ Gerando '{layer_id}' ({res[0]}x{res[1]})...")
                start = time.time()
                
                try:
                    img_bytes = self.comfyui.generate_image(
                        prompt=prompt,
                        width=res[0],
                        height=res[1],
                        steps=gen_config.get("steps", 20),
                        cfg=gen_config.get("cfg", 1.0)
                    )
                    
                    img = Image.open(BytesIO(img_bytes))
                    
                    # Upscale se necessário
                    upscale_to = gen_config.get("upscale_to")
                    if upscale_to:
                        img = img.resize(tuple(upscale_to), Image.LANCZOS)
                    
                    generated_layers[layer_id] = img
                    elapsed = time.time() - start
                    print(f"    ✅ Gerado em {elapsed:.1f}s")
                    
                except Exception as e:
                    print(f"    ❌ Erro: {e}")
                    # Tentar com resolução menor
                    print(f"    🔄 Tentando com resolução reduzida...")
                    try:
                        img_bytes = self.comfyui.generate_image(
                            prompt=prompt,
                            width=res[0] // 2,
                            height=res[1] // 2,
                            steps=gen_config.get("steps", 20) - 5,
                            cfg=gen_config.get("cfg", 1.0)
                        )
                        img = Image.open(BytesIO(img_bytes))
                        target = upscale_to or res
                        img = img.resize(tuple(target), Image.LANCZOS)
                        generated_layers[layer_id] = img
                        print(f"    ✅ Gerado com fallback")
                    except Exception as e2:
                        print(f"    ❌ Fallback falhou: {e2}")
                
                # CRÍTICO: liberar VRAM entre gerações
                print(f"    🧹 Liberando VRAM...")
                self.comfyui.free_memory()
        
        # === FASE 3: PROCESSAMENTO DE FOTOS ===
        print("\n📸 Fase 3: Processando fotos dos hosts...")
        photo_layers = {}
        
        for layer in template["layers"]:
            if layer["type"] in ("cutout_photo", "cutout_photo_or_ai"):
                layer_id = layer["id"]
                layer_plan = plan["layers"].get(layer_id, {})
                photo_source = layer_plan.get("source")
                
                if photo_source:
                    photo_path = Path(ASSETS_DIR) / "hosts" / photo_source
                    if photo_path.exists():
                        print(f"  ✂️ Recortando '{layer_id}': {photo_source}")
                        cutout = self.bg_remover.remove_background(str(photo_path))
                        photo_layers[layer_id] = cutout
                        print(f"    ✅ Recortado")
                    else:
                        print(f"  ⚠️ Foto não encontrada: {photo_path}")
                elif layer["type"] == "cutout_photo_or_ai":
                    # Gerar via AI como fallback
                    flux_prompt = layer_plan.get("flux_prompt", "")
                    if flux_prompt:
                        print(f"  🖼️ Gerando '{layer_id}' via AI...")
                        img_bytes = self.comfyui.generate_image(
                            prompt=flux_prompt,
                            width=512,
                            height=768,
                            steps=15
                        )
                        photo_layers[layer_id] = Image.open(BytesIO(img_bytes))
                        self.comfyui.free_memory()
        
        # === FASE 4: RENDERIZAÇÃO DE TEXTO ===
        print("\n✍️ Fase 4: Renderizando textos...")
        text_layers = {}
        
        for layer in template["layers"]:
            if layer["type"] == "text_rendered":
                layer_id = layer["id"]
                text_key = layer_id.replace("text_", "text_")  # text_top, text_bottom
                text_content = plan["texts"].get(text_key) or plan["texts"].get(layer_id)
                
                if not text_content:
                    if layer.get("optional"):
                        continue
                    text_content = plan["texts"].get("text_top", "")
                
                tc = layer["text_config"]
                layer_size = layer["size"]
                
                # Resolver cores da brand
                color = self._resolve_brand_value(tc.get("color", "#FFFFFF"), brand)
                stroke_color = self._resolve_brand_value(tc.get("stroke_color", "#000000"), brand)
                highlight_color = brand.get("text", {}).get("highlight", "#FFD700")
                
                # Determinar font size (usar o maior do range)
                font_size = tc.get("font_size_range", [72, 96])[-1]
                
                print(f"  📝 Renderizando '{layer_id}': \"{text_content}\"")
                
                output_path = str(self.temp_dir / f"{layer_id}.png")
                render_text_sync(
                    text=text_content,
                    width=layer_size["w"],
                    height=layer_size["h"],
                    font_family=self._resolve_brand_value(
                        tc.get("font_family", "Montserrat"), brand
                    ),
                    font_weight=tc.get("font_weight", 900),
                    font_size=font_size,
                    color=color,
                    stroke_width=tc.get("stroke_width", 4),
                    stroke_color=stroke_color,
                    text_transform=tc.get("text_transform", "uppercase"),
                    letter_spacing=tc.get("letter_spacing", 2),
                    highlight_color=highlight_color,
                    output_path=output_path
                )
                
                text_layers[layer_id] = Image.open(output_path)
                print(f"    ✅ Renderizado")
        
        # === FASE 5: COMPOSIÇÃO FINAL ===
        print("\n🏗️ Fase 5: Compondo thumbnail final...")
        compositor = ThumbCompositor(
            width=template["canvas"]["width"],
            height=template["canvas"]["height"]
        )
        
        # Ordenar camadas por z_index
        sorted_layers = sorted(template["layers"], key=lambda l: l.get("z_index", 0))
        
        for layer in sorted_layers:
            layer_id = layer["id"]
            position = (layer["position"]["x"], layer["position"]["y"])
            size = (layer["size"]["w"], layer["size"]["h"]) if "size" in layer else None
            effects = layer.get("effects", [])
            
            # Resolver cores dinâmicas nos efeitos
            resolved_effects = self._resolve_effects(effects, brand, plan)
            blend = next(
                (e.get("mode") for e in effects if e["type"] == "blend_mode"),
                "normal"
            )
            
            img = None
            
            if layer["type"] == "ai_generated" and layer_id in generated_layers:
                img = generated_layers[layer_id]
            elif layer["type"] in ("cutout_photo", "cutout_photo_or_ai") and layer_id in photo_layers:
                img = photo_layers[layer_id]
            elif layer["type"] == "text_rendered" and layer_id in text_layers:
                img = text_layers[layer_id]
            elif layer["type"] == "shape":
                if layer.get("shape") == "rounded_rect_border":
                    border_color = self._resolve_brand_value(
                        layer.get("color", "#FF0000"), brand
                    )
                    compositor.add_border(
                        color=border_color,
                        width=layer.get("border_width", 6),
                        radius=layer.get("border_radius", 0)
                    )
                continue
            
            if img:
                compositor.add_layer(
                    image=img,
                    position=position,
                    size=size,
                    effects=resolved_effects,
                    blend_mode=blend
                )
                print(f"  📐 Camada '{layer_id}' composta (z:{layer.get('z_index', 0)})")
        
        # === FASE 6: SALVAR OUTPUT ===
        if not output_name:
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
            safe_title = safe_title.strip().replace(" ", "_")[:50]
            output_name = f"thumb_{safe_title}_{int(time.time())}"
        
        output_path = str(self.output_dir / f"{output_name}.png")
        compositor.save(output_path)
        
        print(f"\n{'='*60}")
        print(f"✅ THUMBNAIL GERADA COM SUCESSO!")
        print(f"📁 Arquivo: {output_path}")
        
        # File size
        size_kb = os.path.getsize(output_path) / 1024
        print(f"📦 Tamanho: {size_kb:.0f}KB")
        print(f"{'='*60}\n")
        
        # Cleanup temp
        for f in self.temp_dir.glob("*.png"):
            f.unlink()
        
        return output_path
    
    def _list_host_photos(self, brand: dict) -> list[str]:
        """Lista fotos disponíveis do host."""
        photos_dir = Path(brand.get("host_photos_dir", ""))
        if photos_dir.exists():
            return [f.name for f in photos_dir.glob("*.png")]
        return []
    
    def _resolve_brand_value(self, value, brand: dict):
        """Resolve referências 'from_brand.xxx' para valores reais."""
        if isinstance(value, str) and value.startswith("from_brand"):
            parts = value.split(".")
            current = brand
            for part in parts[1:]:
                current = current.get(part, {})
            return current if isinstance(current, str) else "#FFFFFF"
        return value
    
    def _resolve_effects(self, effects, brand, plan):
        """Resolve cores dinâmicas nos efeitos."""
        resolved = []
        for e in effects:
            e_copy = dict(e)
            if e_copy.get("type") == "blend_mode":
                continue  # Tratado separadamente
            for key, val in e_copy.items():
                if isinstance(val, str):
                    if val == "from_theme":
                        e_copy[key] = brand.get("style", {}).get("glow_color", "#FF6B35")
                    elif val.startswith("from_brand"):
                        e_copy[key] = self._resolve_brand_value(val, brand)
            resolved.append(e_copy)
        return resolved


# === CLI ===
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ThumbForge — YouTube Thumbnail Generator")
    parser.add_argument("title", help="Título do vídeo")
    parser.add_argument("--description", "-d", default="", help="Descrição do vídeo")
    parser.add_argument("--brand", "-b", default="default", help="Brand ID")
    parser.add_argument("--photos", "-p", nargs="*", help="Fotos do host (nomes)")
    parser.add_argument("--output", "-o", help="Nome do arquivo de saída")
    
    args = parser.parse_args()
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Defina ANTHROPIC_API_KEY como variável de ambiente")
        sys.exit(1)
    
    forge = ThumbForge(api_key)
    forge.generate(
        title=args.title,
        description=args.description,
        brand_id=args.brand,
        host_photos=args.photos,
        output_name=args.output
    )
```

### 10.2 `config.py`

```python
"""
config.py — Configurações e caminhos do ThumbForge
"""
import json
from pathlib import Path

BASE_DIR = Path("C:/ThumbForge")
TEMPLATES_DIR = BASE_DIR / "templates"
BRANDS_DIR = BASE_DIR / "brands"
ASSETS_DIR = BASE_DIR / "assets"
WORKFLOWS_DIR = BASE_DIR / "workflows"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"

def load_template(template_id: str) -> dict:
    path = TEMPLATES_DIR / f"{template_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))

def load_brand(brand_id: str) -> dict:
    path = BRANDS_DIR / f"{brand_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # Fallback para default
    return json.loads((BRANDS_DIR / "default.json").read_text(encoding="utf-8"))
```

---

## 11. GESTÃO DE MEMÓRIA — ESTRATÉGIA PARA 8GB VRAM

### Fluxo de VRAM ao longo do pipeline

```
Fase 2 (Geração AI):
┌────────────────────────────────────┐
│ FLUX Q5_K:       ~5.5GB           │
│ T5-XXL Q4:       ~2.5GB (offload) │  ← --lowvram faz offload pra RAM
│ CLIP-L:          ~0.25GB          │
│ VAE decode:      ~0.2GB           │
│ Latent space:    ~0.3GB           │
│ ─────────────────────────────      │
│ Total VRAM:      ~6.2GB ✅        │
│ RAM sistema:     ~5GB extra       │
└────────────────────────────────────┘
    │
    │  free_memory() → descarrega tudo
    ▼
Fase 3 (rembg):
┌────────────────────────────────────┐
│ U2Net ONNX:      ~0.7GB           │  ← Roda em GPU via ONNX Runtime
│ ─────────────────────────────      │
│ Total VRAM:      ~0.7GB ✅        │
└────────────────────────────────────┘
    │
    ▼
Fase 4-5 (Texto + Composição):
┌────────────────────────────────────┐
│ Pillow + Playwright:  CPU only    │
│ VRAM:            0GB ✅           │
└────────────────────────────────────┘
```

### Regras de ouro:
1. **NUNCA** gere duas imagens FLUX simultaneamente
2. **SEMPRE** chame `free_memory()` entre gerações FLUX
3. rembg roda **DEPOIS** de todas as gerações FLUX
4. Se VRAM estourar: fallback para Q4_K (4.5GB) automático
5. Se ainda estourar: reduzir resolução para 768x432 e upscale depois

---

## 12. USO COM CLAUDE CODE

### 12.1 Como integrar com Claude Code

Claude Code pode executar o pipeline de duas formas:

#### Forma 1: CLI direto

```bash
cd C:\ThumbForge\pipeline
.\venv\Scripts\activate

# Gerar thumb
python thumbforge.py "COMO SE TORNAR UM IMÃ DE ATENÇÃO USANDO ENERGIA SEXUAL" \
  --brand fernandoliberal \
  --description "Vídeo sobre presença magnética e energia pessoal" \
  --photos fernando_intense.png
```

#### Forma 2: Import no Claude Code

```python
# Claude Code pode importar e usar diretamente
import sys
sys.path.insert(0, "C:/ThumbForge/pipeline")

from thumbforge import ThumbForge

forge = ThumbForge(api_key="sk-ant-...")
result = forge.generate(
    title="COMO SE TORNAR UM IMÃ DE ATENÇÃO USANDO ENERGIA SEXUAL",
    description="Vídeo sobre presença magnética e energia pessoal",
    brand_id="fernandoliberal",
    host_photos=["fernando_intense.png"]
)
print(f"Thumb gerada: {result}")
```

#### Forma 3: Batch generation

```python
videos = [
    {
        "title": "DEUS É MENTIROSO?",
        "description": "Debate teológico polêmico",
        "brand": "fernandoliberal",
        "photos": ["fernando_surprised.png", "convidado_shocked.png"]
    },
    {
        "title": "O SEGREDO QUE NINGUÉM CONTA",
        "description": "Desenvolvimento pessoal",
        "brand": "fernandoliberal",
        "photos": ["fernando_serious.png"]
    },
]

forge = ThumbForge(api_key="sk-ant-...")
for video in videos:
    forge.generate(**video)
```

---

## 13. CHECKLIST DE IMPLEMENTAÇÃO PARA CLAUDE CODE

### Ordem de implementação (cada item é um commit):

```
[ ] 1. Criar estrutura de diretórios C:\ThumbForge\*
[ ] 2. Instalar ComfyUI + ComfyUI-GGUF + ComfyUI-Manager
[ ] 3. Download dos modelos (FLUX Q5, T5 Q4, CLIP-L, VAE)
[ ] 4. Testar ComfyUI: iniciar, gerar 1 imagem via UI
[ ] 5. Criar config.py + default brand JSON + 1 template JSON
[ ] 6. Implementar comfyui_client.py + testar generate_image()
[ ] 7. Implementar bg_remover.py + testar com foto real
[ ] 8. Implementar text_renderer.py + testar render_text_sync()
[ ] 9. Implementar compositor.py + testar composição de 3 camadas
[ ] 10. Implementar prompt_engine.py + testar com Claude API
[ ] 11. Implementar thumbforge.py (orquestrador)
[ ] 12. Teste E2E: gerar 1 thumb completa
[ ] 13. Criar todos os templates JSON (5 templates)
[ ] 14. Criar brands JSON (fernandoliberal, olhonocodigo, default)
[ ] 15. Sessão de fotos: capturar 5-10 fotos do host com expressões
[ ] 16. Processar fotos: recortar com rembg, salvar em assets/hosts/
[ ] 17. Teste de stress: gerar 5 thumbs consecutivas, monitorar VRAM
[ ] 18. Ajustar timeouts e fallbacks baseado nos testes
[ ] 19. Criar script start_comfyui.bat para iniciar ComfyUI
[ ] 20. Documentar prompts que performaram bem para referência
```

---

## 14. SCRIPTS DE INICIALIZAÇÃO

### `start_comfyui.bat`

```batch
@echo off
echo ========================================
echo  ThumbForge — Iniciando ComfyUI Server
echo ========================================
cd C:\ThumbForge\comfyui
call .\venv\Scripts\activate
python main.py --listen 0.0.0.0 --port 8188 --lowvram --preview-method auto
pause
```

### `generate_thumb.bat`

```batch
@echo off
echo ========================================
echo  ThumbForge — Gerador de Thumbnails
echo ========================================
cd C:\ThumbForge\pipeline
call .\venv\Scripts\activate
python thumbforge.py %*
pause
```

---

## 15. NOTAS FINAIS

### Performance esperada na RTX 5060 8GB:
- Background (1024x576, 20 steps): ~25-35 segundos
- Elemento central (512x512, 15 steps): ~15-20 segundos
- rembg (por foto): ~2-3 segundos
- Text rendering: ~1-2 segundos
- Composição: <1 segundo
- **Total por thumb: ~60-90 segundos** (dependendo do número de camadas AI)

### Upgrades futuros:
- LoRA de estilo específico (treinar com thumbs do canal)
- FLUX Kontext para edição com referência de foto do host
- Cache de backgrounds populares (fogo, cosmos, etc.)
- API REST para integrar com n8n ou frontend web
- A/B testing automático: gerar 2 variações por vídeo
