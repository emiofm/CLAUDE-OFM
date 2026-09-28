"""Image embedding backends.

These compare *overall visual/content aesthetic* (colour palette, lighting,
setting, clothing, composition, photographic style). No face detection, face
recognition or biometric identification is performed anywhere.
"""
from __future__ import annotations

import io
import threading
from abc import ABC, abstractmethod
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps

from ..logging_conf import get_logger

log = get_logger("EMBEDDING")

DEBUG_MODEL = "debug-color-histogram"


class EmbeddingUnavailableError(RuntimeError):
    pass


def load_image(data: bytes, max_side: int = 1024) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


def l2_normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return x / norms


class ImageEmbedder(ABC):
    model_name: str

    @abstractmethod
    def embed_images(self, images: list[bytes]) -> np.ndarray:
        """Return an (n, d) float32 array of L2-normalised embeddings."""


class HFImageEmbedder(ImageEmbedder):
    """CLIP / SigLIP via Hugging Face transformers (image tower only)."""

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self._lock = threading.Lock()
        self._model = None
        self._processor = None

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch  # noqa: F401
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise EmbeddingUnavailableError(
                "transformers/torch are not installed. Run `pip install -r requirements-ml.txt` "
                f"or set EMBEDDING_MODEL={DEBUG_MODEL} for development."
            ) from exc
        log.info("loading model", model=self.model_name, device=self.device)
        self._processor = AutoProcessor.from_pretrained(self.model_name)
        self._model = AutoModel.from_pretrained(self.model_name).to(self.device).eval()

    def embed_images(self, images: list[bytes]) -> np.ndarray:  # pragma: no cover - heavy
        import torch

        with self._lock:
            self._load()
            pil = [load_image(b) for b in images]
            inputs = self._processor(images=pil, return_tensors="pt").to(self.device)
            with torch.no_grad():
                feats = self._model.get_image_features(**inputs)
            return l2_normalize(feats.cpu().numpy())


class ColorHistogramEmbedder(ImageEmbedder):
    """Dependency-free fallback for development/tests.

    Captures only colour palette, brightness and coarse layout. It is NOT a
    semantic model; use CLIP/SigLIP for real searches.
    """

    model_name = DEBUG_MODEL

    def embed_images(self, images: list[bytes]) -> np.ndarray:
        vecs = []
        for data in images:
            img = load_image(data, max_side=256).resize((64, 64))
            hsv = np.asarray(img.convert("HSV"), dtype=np.float32) / 255.0
            hist, _ = np.histogramdd(
                hsv.reshape(-1, 3), bins=(8, 4, 4), range=((0, 1), (0, 1), (0, 1))
            )
            grid = np.asarray(img.resize((4, 4)), dtype=np.float32).reshape(-1) / 255.0
            vecs.append(np.concatenate([np.sqrt(hist.reshape(-1) / hist.sum()), grid * 0.5]))
        return l2_normalize(np.stack(vecs))


@lru_cache
def get_embedder(model_name: str, device: str = "cpu") -> ImageEmbedder:
    if model_name == DEBUG_MODEL:
        log.warning("using debug colour-histogram embedder (not semantic)")
        return ColorHistogramEmbedder()
    return HFImageEmbedder(model_name, device)


def to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_bytes(data: bytes | None) -> np.ndarray | None:
    if not data:
        return None
    return np.frombuffer(data, dtype=np.float32).copy()
