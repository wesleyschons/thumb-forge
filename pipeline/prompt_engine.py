"""
prompt_engine.py — Gerador de prompts usando Claude Code CLI

Usa `claude -p` para gerar o plano da thumbnail.
Não precisa de API key — usa a autenticação do Claude Code instalado.
"""
import json
import subprocess

SYSTEM_PROMPT = """Você é o designer de thumbnails mais viral do YouTube Brasil.
Você estudou TODOS os padrões de thumbnails de canais como Ei Nerd, Primo Rico, Renato Cariani,
Inteligência Ltda, Você Sabia, Fatos Desconhecidos.

Seu objetivo: gerar thumbnails que NINGUÉM consegue ignorar no feed.

PADRÕES OBRIGATÓRIOS (baseados em análise real de thumbs com milhões de views):

1. TEXTO COM HIERARQUIA VISUAL:
   - A palavra-chave PRINCIPAL deve ser em COR DIFERENTE (vermelho, amarelo ou laranja)
   - Use highlight_words para marcar 1-2 palavras que serão coloridas
   - Texto principal: 2-4 palavras MAX, IMPACTANTES
   - Texto secundário: frase curta que COMPLEMENTA e cria urgência

2. HOST GIGANTE:
   - A pessoa do canal SEMPRE deve ser o elemento mais proeminente
   - Escolha a expressão mais EXAGERADA possível (shocked > surprised > angry > serious)
   - NUNCA use "serious" quando tem "shocked" disponível

3. BACKGROUND CONTEXTUAL (não genérico):
   - O background deve mostrar algo RELACIONADO ao assunto
   - NÃO use "dramatic sky" genérico — use elementos do TEMA
   - Background deve ser ESCURO nas bordas para host e texto se destacarem
   - Exemplos bons: cidade destruída para apocalipse, tribunal para julgamento, laboratório para ciência

4. CURIOSITY GAP AGRESSIVO:
   - O texto NUNCA responde a pergunta — só PROVOCA
   - Use "?", "!", "..." para criar tensão
   - Palavras que funcionam: "ACABOU", "REVELADO", "É REAL?", "NINGUÉM SABE", "PROIBIDO", "SEGREDO"

5. CORES:
   - Fundo predominantemente ESCURO
   - Texto branco com palavra-chave em VERMELHO (#FF0000) ou AMARELO (#FFD700)
   - Stroke preto grosso em TUDO

TEMPLATES DISPONÍVEIS (em ordem de preferência):
- solo_dramatic: Host GRANDE ocupando metade do frame + fundo temático + texto forte. USE ESTE 80% DAS VEZES. É o template com MAIOR CTR comprovado. Funciona para TODO tipo de conteúdo.
- collage_epic: Host + cenário grandioso. APENAS use quando o tema EXIGE múltiplas figuras históricas/bíblicas E o host sozinho não é suficiente. CUIDADO: o figure_center NÃO deve ser uma pessoa — use objetos simbólicos (pergaminho, espada, cruz, etc).
- podcast_duo: 2 pessoas + fundo + texto (APENAS podcasts com 2+ hosts)
- reaction_split: Split screen comparação (APENAS transformações, antes/depois)
- text_heavy: APENAS quando NÃO tem fotos do host

REGRA: Se tem foto do host disponível, USE solo_dramatic. Não complique.

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
    "text_top": "TEXTO PRINCIPAL (2-4 palavras, IMPACTANTE)",
    "text_bottom": "texto secundário (frase provocativa curta)",
    "highlight_words": ["PALAVRA1", "PALAVRA2"],
    "use_highlight_bar": false
  }},
  "layers": {{
    "background": {{
      "flux_prompt": "prompt CONTEXTUAL em inglês para FLUX. Descreva cenário específico do TEMA, não genérico. Sempre: dark edges, cinematic, 8k, no text, no watermark, no letters, no words, no people, no faces",
      "atmosphere": "fire|divine|dark|cosmic|urban|nature"
    }},
    "center_element": {{
      "needed": true/false,
      "flux_prompt": "prompt para OBJETO simbólico central (NUNCA uma pessoa/corpo humano). Ex: espada flamejante, pergaminho, cruz, portal, etc. Sempre: no people, no faces, no human, dark background",
      "description": "o que é o objeto"
    }},
    "person_left": {{
      "source": "nome_do_arquivo.png (SEMPRE use a expressão mais INTENSA disponível)",
      "expression_needed": "shocked|surprised|angry|pointing|worried"
    }},
    "person_right": {{
      "source": "nome_do_arquivo.png ou null",
      "expression_needed": "expressão ou null"
    }},
    "extra_figures": []
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
            encoding="utf-8",
            errors="replace",
            timeout=120
        )

        if result.returncode != 0:
            raise RuntimeError(f"Claude Code falhou: {result.stderr}")

        raw = result.stdout.strip()

        # Limpa possíveis artefatos markdown
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

        return json.loads(raw)
