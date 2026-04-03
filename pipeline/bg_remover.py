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
        alpha_matting: bool = False,
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
