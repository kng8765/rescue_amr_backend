"""face_identification CLI 진입점.

사용 모드:
  - 단건: --image <head_crop.jpg>
  - 배치: --metadata-dir <dir> --crops-dir <dir>
    (crop_kind == "head"인 레코드만 매칭, body crop은 skip)

실행 예:
  python -m survivor_identity.face_identification.main --image survivor_*_head.jpg
  python -m survivor_identity.face_identification.main --metadata-dir ~/captures/metadata --crops-dir ~/captures/crops
"""

from __future__ import annotations

import argparse
import glob
import json
import os

from .config import (
    DEFAULT_CACHE_PATH,
    DEFAULT_CTX_ID,
    DEFAULT_GALLERY_DIR,
    DEFAULT_MODEL_NAME,
    DEFAULT_THRESHOLD,
)
from .recognizer import FaceRecognizer


def load_metadata_records(metadata_dir: str) -> list[dict]:
    """metadata 디렉터리의 모든 JSON 파일을 로드해 레코드 리스트로 반환한다."""
    records: list[dict] = []
    for path in sorted(glob.glob(os.path.join(metadata_dir, "*.json"))):
        with open(path, encoding="utf-8") as handle:
            records.append(json.load(handle))
    return records


def resolve_crop_path(record: dict, crops_dir: str | None) -> str | None:
    """metadata 레코드에서 crop 이미지 경로를 해석한다.

    우선순위: saved_image_path(절대경로) → crop_id + crops_dir 조합.
    """
    saved_path = record.get("saved_image_path")
    if saved_path and os.path.isfile(saved_path):
        return saved_path

    crop_id = record.get("crop_id")
    if crops_dir and crop_id:
        for ext in (".jpg", ".jpeg", ".png"):
            candidate = os.path.join(crops_dir, f"{crop_id}{ext}")
            if os.path.isfile(candidate):
                return candidate
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Identify a person from a pre-cropped head image.",
    )
    parser.add_argument("--image", help="Path to a single head crop image")
    parser.add_argument("--metadata-dir", help="Directory of metadata JSON files")
    parser.add_argument("--crops-dir", help="Directory of crop images for batch mode")
    parser.add_argument("--gallery", default=DEFAULT_GALLERY_DIR)
    parser.add_argument("--cache", default=DEFAULT_CACHE_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--gpu", type=int, default=DEFAULT_CTX_ID, help=">=0 GPU id, <0 CPU")
    parser.add_argument(
        "--rebuild-cache",
        action="store_true",
        help="Force gallery cache rebuild before inference",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.image and not args.metadata_dir:
        raise SystemExit("Provide --image or --metadata-dir")

    if args.rebuild_cache:
        from .gallery_builder import build_gallery_cache

        build_gallery_cache(
            gallery_dir=args.gallery,
            cache_path=args.cache,
            model_name=args.model,
            ctx_id=args.gpu,
        )

    recognizer = FaceRecognizer(
        gallery_dir=args.gallery,
        cache_path=args.cache,
        model_name=args.model,
        threshold=args.threshold,
        ctx_id=args.gpu,
        auto_build_cache=not args.rebuild_cache,
    )

    if args.image:
        print(json.dumps(recognizer.identify(args.image), ensure_ascii=False, indent=2))
        return

    results = []
    for record in load_metadata_records(args.metadata_dir):
        if record.get("crop_kind") != "head":
            continue
        image_path = resolve_crop_path(record, args.crops_dir)
        if image_path is None:
            results.append(
                {
                    "crop_id": record.get("crop_id"),
                    "identity": "unknown",
                    "similarity": 0.0,
                    "matched": False,
                    "error": "crop_not_found",
                }
            )
            continue

        result = recognizer.identify(image_path, crop_id=record.get("crop_id"))
        results.append(result)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
