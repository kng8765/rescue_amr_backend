"""갤러리(등록 인물) 임베딩 캐시 빌더.

알고리즘:
  1. gallery/ 디렉터리의 이미지 파일을 스캔 (파일명 stem = identity)
  2. 각 이미지에 embed_image() 적용 → L2-normalized embedding
  3. NPZ 파일로 일괄 저장 (identities[], embeddings[N×D])

캐시가 stale(갤러리 이미지가 더 최신)이면 자동 재빌드된다.

입력: gallery/*.jpg (등록 인물 사진)
출력: gallery_embeddings.npz (identity 목록 + embedding 행렬)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime, timezone

import cv2
import numpy as np

from .config import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CTX_ID,
    DEFAULT_GALLERY_DIR,
    DEFAULT_MODEL_NAME,
    SUPPORTED_IMAGE_EXTENSIONS,
)
from .embedding import embed_image
from .models import load_models


def iter_gallery_images(gallery_dir: str) -> list[tuple[str, str]]:
    """Return sorted (identity, image_path) pairs from a flat gallery directory."""
    pairs: list[tuple[str, str]] = []
    for path in sorted(glob.glob(os.path.join(gallery_dir, "*"))):
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_IMAGE_EXTENSIONS:
            continue
        identity = os.path.splitext(os.path.basename(path))[0]
        pairs.append((identity, path))
    return pairs


def build_gallery_cache(
    gallery_dir: str,
    cache_path: str,
    model_name: str = DEFAULT_MODEL_NAME,
    ctx_id: int = DEFAULT_CTX_ID,
) -> dict:
    """갤러리 전체 이미지를 임베딩해 NPZ 캐시 파일로 저장한다.

    알고리즘: 각 등록 이미지 → align + ArcFace embed → N×D 행렬로 stack → NPZ 압축 저장.
    """
    pairs = iter_gallery_images(gallery_dir)
    if not pairs:
        raise RuntimeError(f"No gallery images found in {gallery_dir}")

    models = load_models(model_name=model_name, ctx_id=ctx_id)
    identities: list[str] = []
    embeddings: list[np.ndarray] = []
    source_paths: list[str] = []

    for identity, image_path in pairs:
        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise RuntimeError(f"Failed to read gallery image: {image_path}")

        embedding = embed_image(image_bgr, models.recognition, models.landmark)
        if embedding is None:
            raise RuntimeError(f"Failed to align/embed gallery image: {image_path}")

        identities.append(identity)
        embeddings.append(embedding)
        source_paths.append(image_path)

    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    np.savez_compressed(
        cache_path,
        identities=np.array(identities, dtype=object),
        embeddings=np.stack(embeddings).astype(np.float32),
        source_paths=np.array(source_paths, dtype=object),
        model_name=np.array(model_name),
        gallery_dir=np.array(os.path.abspath(gallery_dir)),
        created_at=np.array(datetime.now(timezone.utc).isoformat()),
    )

    return {
        "cache_path": os.path.abspath(cache_path),
        "gallery_dir": os.path.abspath(gallery_dir),
        "model_name": model_name,
        "identities": identities,
        "count": len(identities),
    }


def load_gallery_cache(cache_path: str) -> tuple[list[str], np.ndarray]:
    """Load identities and embeddings from cache."""
    if not os.path.isfile(cache_path):
        raise FileNotFoundError(f"Gallery cache not found: {cache_path}")

    data = np.load(cache_path, allow_pickle=True)
    identities = [str(x) for x in data["identities"].tolist()]
    embeddings = data["embeddings"].astype(np.float32)
    return identities, embeddings


def is_cache_stale(cache_path: str, gallery_dir: str) -> bool:
    """갤러리 이미지가 캐시보다 최신이면 True (재빌드 필요)."""
    if not os.path.isfile(cache_path):
        return True

    cache_mtime = os.path.getmtime(cache_path)
    for _, image_path in iter_gallery_images(gallery_dir):
        if os.path.getmtime(image_path) > cache_mtime:
            return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build gallery embedding cache for face identification.",
    )
    parser.add_argument("--gallery", default=DEFAULT_GALLERY_DIR)
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--gpu", type=int, default=DEFAULT_CTX_ID, help=">=0 GPU id, <0 CPU")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = build_gallery_cache(
        gallery_dir=args.gallery,
        cache_path=args.cache,
        model_name=args.model,
        ctx_id=args.gpu,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
