"""ArcFace 임베딩 추출.

알고리즘 흐름:
  1. align_face() → 112×112 정렬된 얼굴
  2. recognition_model.get_feat() → ArcFace 특징 벡터 (D차원)
  3. L2 정규화 → 단위 벡터 (cosine similarity = dot product)

입력: BGR head crop
출력: L2-normalized float32 embedding (D,) 또는 None (정렬 실패)
"""

from __future__ import annotations

import numpy as np

from .utils.alignment import align_face


def l2_normalize(vector: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    """벡터를 L2 norm으로 나눠 단위 벡터로 만든다 (cosine similarity 계산용)."""
    return vector / (np.linalg.norm(vector) + eps)


def embed_image(
    image_bgr: np.ndarray,
    recognition_model,
    landmark_model,
) -> np.ndarray | None:
    """BGR 이미지에서 L2 정규화된 ArcFace 임베딩을 추출한다.

    알고리즘: landmark 정렬 → ArcFace feature 추출 → L2 normalize.
    """
    aligned = align_face(image_bgr, landmark_model)
    if aligned is None:
        return None
    # ArcFace recognition model (MobileFaceNet) forward pass
    feat = recognition_model.get_feat(aligned).flatten().astype(np.float32)
    return l2_normalize(feat)
