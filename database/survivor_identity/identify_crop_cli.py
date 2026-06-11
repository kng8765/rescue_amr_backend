"""CLI entry point for identifying one crop image."""

from __future__ import annotations

import argparse
import json
import os

from survivor_identity.face_identifier import FaceIdentifier
from survivor_identity.gallery_store import load_config, with_overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Identify one survivor crop image.")
    parser.add_argument("--image", required=True, help="Path to a head/body/face crop")
    parser.add_argument("--input-id", default=None)
    parser.add_argument("--input-kind", default=None, help="head, body, face, or crop")
    parser.add_argument("--parent-detection-id", default="")
    parser.add_argument("--config", default=None, help="identity.yaml path")
    parser.add_argument("--gallery", default=None, help="Central gallery directory")
    parser.add_argument("--cache", default=None, help="Gallery cache .npz path")
    parser.add_argument("--model", default=None, help="InsightFace recognition pack")
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--gpu", type=int, default=None, help=">=0 GPU id, <0 CPU")
    parser.add_argument("--rebuild-cache", action="store_true")
    parser.add_argument("--output-json", default=None, help="Optional result JSON path")
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
    )
    identifier = FaceIdentifier(config, rebuild_cache=args.rebuild_cache)
    result = identifier.identify_path(
        args.image,
        input_id=args.input_id,
        input_kind=args.input_kind,
        parent_detection_id=args.parent_detection_id,
    )
    payload = result.to_dict()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.output_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
        with open(args.output_json, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
