"""face_identification 기본 설정값.

- DEFAULT_MODEL_NAME: ArcFace recognition pack (buffalo_sc, ~15MB MobileFaceNet)
- DEFAULT_THRESHOLD: cosine similarity 임계값 (0.40, 미만이면 unknown)
- DEFAULT_GALLERY_DIR / DEFAULT_CACHE_PATH: 등록 인물 이미지 및 NPZ 캐시 경로
"""

from __future__ import annotations

import os

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_SOURCE_GALLERY_DIR = os.path.abspath(os.path.join(_PKG_DIR, "..", "..", "gallery"))


def _default_gallery_dir() -> str:
    try:
        from ament_index_python.packages import get_package_share_directory

        return os.path.join(get_package_share_directory("survivor_identity"), "gallery")
    except Exception:  # noqa: BLE001
        return _SOURCE_GALLERY_DIR

DEFAULT_MODEL_NAME = "buffalo_sc"
DEFAULT_THRESHOLD = 0.40
DEFAULT_CTX_ID = -1  # CPU
DEFAULT_GALLERY_DIR = _default_gallery_dir()
DEFAULT_CACHE_PATH = os.path.join(DEFAULT_GALLERY_DIR, "gallery_embeddings.npz")

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
