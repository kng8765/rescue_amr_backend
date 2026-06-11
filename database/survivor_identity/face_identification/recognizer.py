"""생존자 1:N 얼굴 식별 (ArcFace + Cosine Similarity).

전체 알고리즘:
  [입력] head crop 이미지 (perception_node에서 저장된 JPG)
    ↓
  [1] 106-point landmark 추론 (2d106det)
    ↓
  [2] 106→5 keypoint 축소 + similarity transform 정렬 (112×112)
    ↓
  [3] ArcFace embedding 추출 + L2 정규화
    ↓
  [4] 1:N 매칭: gallery embedding 행렬과 dot product → cosine similarity
    ↓
  [5] argmax + threshold(기본 0.40) → identity 또는 "unknown"

출력: {identity, similarity, matched, crop_id?, image_path?, error?}
"""

from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np

from .config import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CTX_ID,
    DEFAULT_GALLERY_DIR,
    DEFAULT_MODEL_NAME,
    DEFAULT_THRESHOLD,
)
from .embedding import embed_image, l2_normalize
from .gallery_builder import (
    build_gallery_cache,
    is_cache_stale,
    load_gallery_cache,
)
from .models import load_models


class FaceRecognizer:
    """pre-cropped head 이미지로 1:N 얼굴 식별을 수행하는 메인 API.

    초기화 시 갤러리 캐시를 로드하고, stale이면 자동 재빌드한다.
    identify() / identify_image()로 단건 식별, match_embedding()으로
    임베딩만으로 갤러리 대조가 가능하다.
    """

    def __init__(
        self,
        gallery_dir: str = DEFAULT_GALLERY_DIR,
        cache_path: str = DEFAULT_CACHE_PATH,
        model_name: str = DEFAULT_MODEL_NAME,
        threshold: float = DEFAULT_THRESHOLD,
        ctx_id: int = DEFAULT_CTX_ID,
        auto_build_cache: bool = True,
    ) -> None:
        self.gallery_dir = os.path.abspath(gallery_dir)
        self.cache_path = os.path.abspath(cache_path)
        self.model_name = model_name
        self.threshold = threshold
        self.ctx_id = ctx_id

        if auto_build_cache and is_cache_stale(self.cache_path, self.gallery_dir):
            build_gallery_cache(
                gallery_dir=self.gallery_dir,
                cache_path=self.cache_path,
                model_name=self.model_name,
                ctx_id=self.ctx_id,
            )

        self.labels, self.templates = load_gallery_cache(self.cache_path)
        if len(self.labels) == 0:
            raise RuntimeError(f"Gallery cache is empty: {self.cache_path}")

        self.models = load_models(model_name=self.model_name, ctx_id=self.ctx_id)

    def identify(self, image_path: str, crop_id: str | None = None) -> dict[str, Any]:
        """Identify a person from an image file path."""
        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            return self._result(
                identity="unknown",
                similarity=0.0,
                matched=False,
                image_path=image_path,
                crop_id=crop_id,
                error="image_read_failed",
            )
        return self.identify_image(
            image_bgr,
            image_path=image_path,
            crop_id=crop_id,
        )

    def identify_image(
        self,
        image_bgr: np.ndarray,
        image_path: str | None = None,
        crop_id: str | None = None,
    ) -> dict[str, Any]:
        """Identify a person from a BGR image array."""
        embedding = embed_image(image_bgr, self.models.recognition, self.models.landmark)
        if embedding is None:
            return self._result(
                identity="unknown",
                similarity=0.0,
                matched=False,
                image_path=image_path,
                crop_id=crop_id,
                error="alignment_failed",
            )

        identity, similarity = self.match_embedding(embedding)
        matched = identity != "unknown"
        return self._result(
            identity=identity,
            similarity=similarity,
            matched=matched,
            image_path=image_path,
            crop_id=crop_id,
        )

    def match_embedding(self, embedding: np.ndarray) -> tuple[str, float]:
        """정규화된 query embedding을 갤러리 전체와 1:N 대조한다.

        알고리즘: L2-normalized 벡터끼리 dot product = cosine similarity.
        gallery 전체와 내적 후 argmax; 최고 유사도가 threshold 미만이면 "unknown".
        """
        query = l2_normalize(np.asarray(embedding, dtype=np.float32))
        # 1:N cosine similarity: (N×D) @ (D,) → (N,) similarity scores
        similarities = self.templates @ query
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        if best_sim >= self.threshold:
            return self.labels[best_idx], best_sim
        return "unknown", best_sim

    @staticmethod
    def _result(
        identity: str,
        similarity: float,
        matched: bool,
        image_path: str | None = None,
        crop_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "identity": identity,
            "similarity": round(similarity, 4),
            "matched": matched,
        }
        if crop_id is not None:
            result["crop_id"] = crop_id
        if image_path is not None:
            result["image_path"] = image_path
        if error is not None:
            result["error"] = error
        return result
