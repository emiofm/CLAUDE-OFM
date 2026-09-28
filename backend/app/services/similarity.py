"""Visual similarity between a reference centroid and candidate images."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .embeddings import l2_normalize


def centroid(embeddings: np.ndarray) -> np.ndarray:
    """Mean of L2-normalised embeddings, re-normalised."""
    emb = l2_normalize(np.atleast_2d(embeddings))
    if emb.shape[0] == 0:
        raise ValueError("at least one embedding is required")
    return l2_normalize(emb.mean(axis=0))


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(l2_normalize(a), l2_normalize(b)))


def cosine_to_score(cos: float, floor: float = 0.0, ceiling: float = 1.0) -> float:
    """Map a cosine similarity to 0-100 using a calibratable linear window.

    CLIP-style image embeddings rarely go below ~0.4 for natural photos, so
    ``floor``/``ceiling`` (configurable in Settings) spread the useful range.
    """
    if ceiling <= floor:
        raise ValueError("ceiling must be greater than floor")
    return float(np.clip((cos - floor) / (ceiling - floor), 0.0, 1.0) * 100.0)


@dataclass
class CreatorSimilarity:
    score: float | None  # combined 0-100
    best: float | None
    top_k_avg: float | None
    images_analyzed: int
    best_index: int | None


def aggregate_creator_similarity(
    image_scores: list[float],
    *,
    best_weight: float = 0.7,
    top_k_weight: float = 0.3,
    top_k: int = 5,
) -> CreatorSimilarity:
    """Combine per-image scores: default 70% best image + 30% mean of top 5."""
    if not image_scores:
        return CreatorSimilarity(None, None, None, 0, None)
    arr = np.asarray(image_scores, dtype=np.float64)
    best_idx = int(arr.argmax())
    best = float(arr[best_idx])
    top = np.sort(arr)[::-1][: max(1, top_k)]
    top_avg = float(top.mean())
    total_w = best_weight + top_k_weight
    if total_w <= 0:
        best_weight, top_k_weight, total_w = 0.7, 0.3, 1.0
    combined = (best_weight * best + top_k_weight * top_avg) / total_w
    return CreatorSimilarity(round(combined, 2), round(best, 2), round(top_avg, 2), len(arr), best_idx)
