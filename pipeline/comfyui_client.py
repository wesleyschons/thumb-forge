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
                "class_type": "DualCLIPLoaderGGUF",
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
            time.sleep(2)
        except Exception:
            pass

    def close(self):
        if self.ws:
            self.ws.close()
