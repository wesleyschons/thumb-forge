"""
prompt_engine.py — Gerador de prompts usando Claude Code CLI

Usa `claude -p` para gerar o plano da thumbnail.
Não precisa de API key — usa a autenticação do Claude Code instalado.
"""
import json
import subprocess

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
    def __init__(self):
        pass

    def generate_thumb_plan(
        self,
        title: str,
        description: str,
        brand_id: str,
        available_photos: list[str],
        templates: list[str]
    ) -> dict:
        """Gera o plano completo da thumbnail via Claude Code CLI."""

        user_prompt = GENERATION_PROMPT_TEMPLATE.format(
            title=title,
            description=description,
            brand_id=brand_id,
            available_photos=json.dumps(available_photos),
            templates=json.dumps(templates)
        )

        full_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt

        result = subprocess.run(
            ["claude", "-p", full_prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude Code falhou: {result.stderr}")

        raw = result.stdout.strip()

        # Limpa possíveis artefatos markdown
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

        return json.loads(raw)
