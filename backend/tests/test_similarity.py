import numpy as np
import pytest

from app.services.embeddings import ColorHistogramEmbedder, from_bytes, to_bytes
from app.services.similarity import aggregate_creator_similarity, centroid, cosine, cosine_to_score
from tests.conftest import BLUE, BROWN, make_image


def test_centroid_is_normalised_mean():
    c = centroid(np.array([[1.0, 0.0], [0.0, 1.0]]))
    assert np.allclose(c, [2 ** -0.5, 2 ** -0.5])
    assert np.isclose(np.linalg.norm(c), 1.0)


def test_cosine_to_score_window():
    assert cosine_to_score(0.5, 0.5, 0.95) == 0
    assert cosine_to_score(0.95, 0.5, 0.95) == 100
    assert cosine_to_score(0.725, 0.5, 0.95) == pytest.approx(50)
    assert cosine_to_score(-1, 0.5, 0.95) == 0
    with pytest.raises(ValueError):
        cosine_to_score(0.5, 0.9, 0.1)


def test_creator_aggregation_default_70_30():
    scores = [90, 80, 70, 60, 50, 10]
    agg = aggregate_creator_similarity(scores)
    top5 = (90 + 80 + 70 + 60 + 50) / 5
    assert agg.best == 90
    assert agg.top_k_avg == top5
    assert agg.score == pytest.approx(0.7 * 90 + 0.3 * top5)
    assert agg.images_analyzed == 6
    assert agg.best_index == 0


def test_aggregation_no_images_is_unavailable():
    agg = aggregate_creator_similarity([])
    assert agg.score is None and agg.images_analyzed == 0


def test_embedding_roundtrip():
    v = np.random.default_rng(0).normal(size=16).astype(np.float32)
    assert np.allclose(from_bytes(to_bytes(v)), v)
    assert from_bytes(None) is None


def test_similar_aesthetic_scores_higher_than_different():
    emb = ColorHistogramEmbedder()
    refs = emb.embed_images([make_image(BROWN, seed=i) for i in range(3)])
    c = centroid(refs)
    similar = emb.embed_images([make_image((125, 85, 55), seed=10)])[0]
    different = emb.embed_images([make_image(BLUE, seed=11)])[0]
    assert cosine(c, similar) > cosine(c, different)
    assert np.allclose(np.linalg.norm(refs, axis=1), 1.0, atol=1e-5)
