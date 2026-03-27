"""
text_renderer.py — Renderiza texto da thumb via Chrome headless

Gera HTML com CSS styled text -> screenshot via Playwright -> PNG transparente.
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
    font-family: '{font_family_css}', Impact, Arial Black, sans-serif;
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

        # font_family para URL (com +) e para CSS (com espaço)
        font_family_url = font_family.replace(" ", "+")
        font_family_css = font_family

        html = HTML_TEMPLATE.format(
            font_family=font_family_url,
            font_family_css=font_family_css,
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
            omit_background=True,
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
