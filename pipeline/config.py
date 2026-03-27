"""
config.py — Configurações e caminhos do ThumbForge

Todos os paths apontam para D:\Dev\ThumbForge no Windows.
"""
import json
from pathlib import Path

BASE_DIR = Path("D:/Dev/ThumbForge")
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
    return json.loads((BRANDS_DIR / "default.json").read_text(encoding="utf-8"))
