import io
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cf-tests-"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_TMP / 'test.db'}",
        "EMBEDDING_MODEL": "debug-color-histogram",
        "REFERENCE_UPLOAD_DIR": str(_TMP / "refs"),
        "THREADS_APP_ID": "123",
        "THREADS_APP_SECRET": "super-secret-value",
        "THREADS_ACCESS_TOKEN": "",
        "FRONTEND_URL": "http://frontend.test",
    }
)

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from PIL import Image  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def make_image(rgb, seed=0, size=(96, 96), fmt="PNG") -> bytes:
    rng = np.random.default_rng(seed)
    arr = np.clip(np.array(rgb, dtype=np.float32) + rng.normal(0, 12, (*size, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return buf.getvalue()


BROWN = (120, 80, 50)
BLUE = (40, 70, 200)
