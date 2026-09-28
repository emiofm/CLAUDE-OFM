"""Download the configured CLIP/SigLIP model once, so the first search is fast.

Used by the Windows launcher. Exit code 0 = ready (or debug embedder in use).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.embeddings import DEBUG_MODEL  # noqa: E402


def main() -> int:
    model = get_settings().embedding_model
    if model == DEBUG_MODEL:
        print(f"Embedding model: {model} (nothing to download)")
        return 0
    try:
        from transformers import AutoModel, AutoProcessor
    except ImportError:
        print("transformers/torch are not installed", file=sys.stderr)
        return 1
    print(f"Downloading {model} ...")
    AutoProcessor.from_pretrained(model)
    AutoModel.from_pretrained(model)
    print("Model ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
