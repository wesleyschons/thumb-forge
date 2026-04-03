"""
compositor.py — Composição de camadas via Pillow

Recebe lista de camadas (imagens + configurações) e compõe a thumb final.
Suporta: blend modes, drop shadow, glow, vignette, color grading, rim light.
"""
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw
import numpy as np


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

        if size:
            layer = self._fit_preserve_aspect(layer, size)

        if effects:
            for effect in effects:
                layer = self._apply_effect(layer, effect)

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
        arr = np.array(img)
        alpha = arr[:, :, 3]

        gradient = np.zeros((h, w), dtype=np.float32)
        if side == "right":
            for x in range(w):
                gradient[:, x] = (x / w) ** 2
        else:
            for x in range(w):
                gradient[:, x] = (1 - x / w) ** 2

        # Detectar bordas para aplicar rim light
        try:
            from scipy.ndimage import sobel
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
        region = self.canvas.crop((
            position[0], position[1],
            position[0] + layer.width,
            position[1] + layer.height
        ))

        arr_base = np.array(region).astype(float) / 255
        arr_layer = np.array(layer).astype(float) / 255

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
    def _fit_preserve_aspect(img: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Redimensiona mantendo aspect ratio, encaixando dentro do size."""
        target_w, target_h = size
        orig_w, orig_h = img.size
        ratio = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * ratio)
        new_h = int(orig_h * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        # Criar canvas transparente no tamanho alvo, centralizar imagem
        result = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
        offset_x = (target_w - new_w) // 2
        offset_y = target_h - new_h  # Alinhar embaixo (pessoas ancoradas ao chão)
        result.paste(resized, (offset_x, offset_y), resized)
        return result

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return (r, g, b, alpha)
