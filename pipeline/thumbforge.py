"""
thumbforge.py — Orquestrador principal do ThumbForge

Fluxo:
1. Recebe briefing (título + descrição + brand)
2. Claude gera plano da thumb (template + prompts + textos)
3. Para cada camada AI: chama ComfyUI -> gera imagem
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
from pathlib import Path
from PIL import Image
from io import BytesIO

from config import load_template, load_brand, TEMPLATES_DIR, BRANDS_DIR, ASSETS_DIR, TEMP_DIR, OUTPUT_DIR
from prompt_engine import PromptEngine
from comfyui_client import ComfyUIClient
from compositor import ThumbCompositor
from text_renderer import TextRenderer, render_text_sync
from bg_remover import BackgroundRemover


class ThumbForge:
    def __init__(self):
        self.prompt_engine = PromptEngine()
        self.comfyui = ComfyUIClient()
        self.bg_remover = BackgroundRemover(model_name="u2net_human_seg")
        self.text_renderer = TextRenderer()

        self.temp_dir = TEMP_DIR
        self.output_dir = OUTPUT_DIR
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
        print(f"ThumbForge — Gerando thumbnail")
        print(f"Titulo: {title}")
        print(f"Brand: {brand_id}")
        print(f"{'='*60}\n")

        # === FASE 1: PLANEJAMENTO (Claude API) ===
        print("Fase 1: Gerando plano com Claude...")
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

        print(f"  Template: {plan['template_id']}")
        print(f"  Texto principal: {plan['texts']['text_top']}")
        print(f"  Texto secundario: {plan['texts'].get('text_bottom', 'nenhum')}")
        print(f"  Razao: {plan.get('reasoning', '')}")

        # Salvar plano para debug
        plan_path = self.temp_dir / "current_plan.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

        # === FASE 2: GERAÇÃO DE IMAGENS AI (ComfyUI) ===
        print("\nFase 2: Gerando imagens com FLUX...")
        template = load_template(plan["template_id"])
        generated_layers = {}

        for layer in template["layers"]:
            if layer["type"] == "ai_generated":
                layer_id = layer["id"]
                layer_plan = plan["layers"].get(layer_id, {})

                # Skip se opcional e não necessário
                if layer.get("optional") and not layer_plan.get("needed", False):
                    print(f"  Camada '{layer_id}' — skip (opcional)")
                    continue

                prompt = layer_plan.get("flux_prompt", "")
                if not prompt:
                    prompt = layer["generation"]["prompt_context"]

                gen_config = layer["generation"]
                res = gen_config.get("resolution", [1024, 576])

                print(f"  Gerando '{layer_id}' ({res[0]}x{res[1]})...")
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
                    print(f"    Gerado em {elapsed:.1f}s")

                except Exception as e:
                    print(f"    ERRO: {e}")
                    # Tentar com resolução menor
                    print(f"    Tentando com resolução reduzida...")
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
                        print(f"    Gerado com fallback")
                    except Exception as e2:
                        print(f"    Fallback falhou: {e2}")

                # CRÍTICO: liberar VRAM entre gerações
                print(f"    Liberando VRAM...")
                self.comfyui.free_memory()

        # === FASE 3: PROCESSAMENTO DE FOTOS ===
        print("\nFase 3: Processando fotos dos hosts...")
        photo_layers = {}

        for layer in template["layers"]:
            if layer["type"] in ("cutout_photo", "cutout_photo_or_ai"):
                layer_id = layer["id"]
                layer_plan = plan["layers"].get(layer_id, {})
                photo_source = layer_plan.get("source")

                if photo_source:
                    photo_path = Path(ASSETS_DIR) / "hosts" / photo_source
                    if photo_path.exists():
                        print(f"  Recortando '{layer_id}': {photo_source}")
                        cutout = self.bg_remover.remove_background(str(photo_path))
                        photo_layers[layer_id] = cutout
                        print(f"    Recortado")
                    else:
                        print(f"  AVISO: Foto nao encontrada: {photo_path}")
                elif layer["type"] == "cutout_photo_or_ai":
                    # Gerar via AI como fallback
                    flux_prompt = layer_plan.get("flux_prompt", "")
                    if flux_prompt:
                        print(f"  Gerando '{layer_id}' via AI...")
                        img_bytes = self.comfyui.generate_image(
                            prompt=flux_prompt,
                            width=512,
                            height=768,
                            steps=15
                        )
                        photo_layers[layer_id] = Image.open(BytesIO(img_bytes))
                        self.comfyui.free_memory()

        # === FASE 4: RENDERIZAÇÃO DE TEXTO ===
        print("\nFase 4: Renderizando textos...")
        text_layers = {}

        for layer in template["layers"]:
            if layer["type"] == "text_rendered":
                layer_id = layer["id"]
                text_key = layer_id.replace("text_", "text_")
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

                print(f"  Renderizando '{layer_id}': \"{text_content}\"")

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
                print(f"    Renderizado")

        # === FASE 5: COMPOSIÇÃO FINAL ===
        print("\nFase 5: Compondo thumbnail final...")
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
                print(f"  Camada '{layer_id}' composta (z:{layer.get('z_index', 0)})")

        # === FASE 6: SALVAR OUTPUT ===
        if not output_name:
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)
            safe_title = safe_title.strip().replace(" ", "_")[:50]
            output_name = f"thumb_{safe_title}_{int(time.time())}"

        output_path = str(self.output_dir / f"{output_name}.png")
        compositor.save(output_path)

        print(f"\n{'='*60}")
        print(f"THUMBNAIL GERADA COM SUCESSO!")
        print(f"Arquivo: {output_path}")

        size_kb = os.path.getsize(output_path) / 1024
        print(f"Tamanho: {size_kb:.0f}KB")
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
                continue
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
    parser.add_argument("title", help="Titulo do video")
    parser.add_argument("--description", "-d", default="", help="Descricao do video")
    parser.add_argument("--brand", "-b", default="default", help="Brand ID")
    parser.add_argument("--photos", "-p", nargs="*", help="Fotos do host (nomes)")
    parser.add_argument("--output", "-o", help="Nome do arquivo de saida")

    args = parser.parse_args()

    forge = ThumbForge()
    forge.generate(
        title=args.title,
        description=args.description,
        brand_id=args.brand,
        host_photos=args.photos,
        output_name=args.output
    )
