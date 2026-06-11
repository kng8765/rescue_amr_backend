"""Folder/mock-queue worker for central survivor identity requests."""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any

from survivor_identity.face_identifier import FaceIdentifier
from survivor_identity.gallery_store import load_config, with_overrides

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a folder/mock queue and write identity result JSON files.",
    )
    parser.add_argument("--input-dir", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--config", default=None)
    parser.add_argument("--gallery", default=None)
    parser.add_argument("--cache", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--gpu", type=int, default=None)
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll-period", type=float, default=2.0)
    args, _ = parser.parse_known_args()
    return args


def main() -> int:
    args = parse_args()
    config = with_overrides(
        load_config(args.config),
        gallery_dir=args.gallery,
        cache_path=args.cache,
        model_name=args.model,
        threshold=args.threshold,
        ctx_id=args.gpu,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
    )
    os.makedirs(config.input_dir, exist_ok=True)
    os.makedirs(config.output_dir, exist_ok=True)

    print(
        f"identity_worker input_dir='{config.input_dir}' "
        f"output_dir='{config.output_dir}' threshold={config.threshold}"
    )

    identifier: FaceIdentifier | None = None
    while True:
        requests = iter_requests(config.input_dir)
        if requests and identifier is None:
            identifier = FaceIdentifier(config, rebuild_cache=args.rebuild_cache)
        processed = (
            scan_requests(identifier, requests, config.output_dir)
            if identifier is not None else 0
        )
        print(f"processed {processed} identity request(s)")
        if not args.watch:
            break
        time.sleep(max(0.1, float(args.poll_period)))
    return 0


def scan_once(identifier: FaceIdentifier, input_dir: str, output_dir: str) -> int:
    return scan_requests(identifier, iter_requests(input_dir), output_dir)


def scan_requests(identifier: FaceIdentifier, requests: list[str], output_dir: str) -> int:
    count = 0
    for path in requests:
        request = load_request(path)
        if request is None:
            continue
        output_path = result_path(output_dir, request["input_id"])
        if os.path.exists(output_path):
            continue
        result = identifier.identify_path(
            request["image_path"],
            input_id=request["input_id"],
            input_kind=request["input_kind"],
            parent_detection_id=request["parent_detection_id"],
        )
        write_json(output_path, result.to_dict())
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        count += 1
    return count


def iter_requests(input_dir: str) -> list[str]:
    paths = []
    for name in sorted(os.listdir(input_dir)):
        path = os.path.join(input_dir, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext == ".json" or ext in IMAGE_EXTENSIONS:
            paths.append(path)
    return paths


def load_request(path: str) -> dict[str, str] | None:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, encoding="utf-8") as handle:
            metadata = json.load(handle)
        image_path = resolve_image_path(metadata)
        if not image_path:
            return None
        input_id = str(
            metadata.get("crop_id")
            or metadata.get("detection_id")
            or os.path.splitext(os.path.basename(image_path))[0]
        )
        return {
            "image_path": image_path,
            "input_id": input_id,
            "input_kind": str(metadata.get("crop_kind") or infer_kind(image_path)),
            "parent_detection_id": str(metadata.get("parent_detection_id") or ""),
        }

    if ext in IMAGE_EXTENSIONS:
        return {
            "image_path": os.path.abspath(path),
            "input_id": os.path.splitext(os.path.basename(path))[0],
            "input_kind": infer_kind(path),
            "parent_detection_id": "",
        }
    return None


def resolve_image_path(metadata: dict[str, Any]) -> str | None:
    saved = metadata.get("saved_image_path")
    if saved and os.path.isfile(str(saved)):
        return os.path.abspath(str(saved))

    image_uri = str(metadata.get("image_uri") or "")
    if image_uri.startswith("file://"):
        candidate = image_uri[len("file://"):]
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def infer_kind(image_path: str) -> str:
    stem = os.path.splitext(os.path.basename(image_path))[0].lower()
    if stem.endswith("_head") or "_head_" in stem:
        return "head"
    if stem.endswith("_body") or "_body_" in stem:
        return "body"
    if stem.startswith("face_") or "_face" in stem:
        return "face"
    return "crop"


def result_path(output_dir: str, input_id: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in input_id)
    return os.path.join(output_dir, f"{safe}_identity.json")


def write_json(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
