"""Gallery and cache management for central survivor identity matching."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import numpy as np
from ament_index_python.packages import get_package_share_directory

from survivor_identity.face_identification.config import (
    DEFAULT_CTX_ID,
    DEFAULT_MODEL_NAME,
)


@dataclass(frozen=True)
class IdentityConfig:
    """Central identity runtime settings."""

    gallery_dir: str
    cache_path: str
    model_name: str = DEFAULT_MODEL_NAME
    threshold: float = 0.40
    ctx_id: int = DEFAULT_CTX_ID
    input_dir: str = "/tmp/survivor_identity/inbox"
    output_dir: str = "/tmp/survivor_identity/results"


def package_share_dir() -> str:
    try:
        return get_package_share_directory("survivor_identity")
    except Exception:  # noqa: BLE001
        return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def default_gallery_dir() -> str:
    return os.path.join(package_share_dir(), "gallery")


def default_cache_path() -> str:
    return os.path.join(package_share_dir(), "gallery", "gallery_embeddings.npz")


def default_config_path() -> str:
    return os.path.join(package_share_dir(), "config", "identity.yaml")


def load_config(config_path: str | None = None) -> IdentityConfig:
    """Load identity config from YAML, falling back to package defaults."""

    path = config_path or default_config_path()
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("python3-yaml is required to read identity.yaml") from exc
        with open(path, encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        data = loaded.get("survivor_identity", {}).get("ros__parameters", loaded)

    gallery_dir = str(data.get("gallery_dir") or default_gallery_dir())
    cache_path = str(data.get("cache_path") or os.path.join(gallery_dir, "gallery_embeddings.npz"))
    return IdentityConfig(
        gallery_dir=gallery_dir,
        cache_path=cache_path,
        model_name=str(data.get("model_name") or DEFAULT_MODEL_NAME),
        threshold=float(data.get("threshold", 0.40)),
        ctx_id=int(data.get("ctx_id", DEFAULT_CTX_ID)),
        input_dir=str(data.get("input_dir") or "/tmp/survivor_identity/inbox"),
        output_dir=str(data.get("output_dir") or "/tmp/survivor_identity/results"),
    )


def with_overrides(
    config: IdentityConfig,
    *,
    gallery_dir: str | None = None,
    cache_path: str | None = None,
    model_name: str | None = None,
    threshold: float | None = None,
    ctx_id: int | None = None,
    input_dir: str | None = None,
    output_dir: str | None = None,
) -> IdentityConfig:
    gallery = os.path.abspath(gallery_dir) if gallery_dir else config.gallery_dir
    cache = os.path.abspath(cache_path) if cache_path else (
        os.path.join(gallery, "gallery_embeddings.npz")
        if gallery_dir and not cache_path else config.cache_path
    )
    return IdentityConfig(
        gallery_dir=gallery,
        cache_path=cache,
        model_name=model_name or config.model_name,
        threshold=config.threshold if threshold is None else float(threshold),
        ctx_id=config.ctx_id if ctx_id is None else int(ctx_id),
        input_dir=os.path.abspath(input_dir) if input_dir else config.input_dir,
        output_dir=os.path.abspath(output_dir) if output_dir else config.output_dir,
    )


class GalleryStore:
    """Loads or refreshes the single central gallery embedding cache."""

    def __init__(self, config: IdentityConfig, *, rebuild_cache: bool = False) -> None:
        self.config = config
        self.rebuild_cache = rebuild_cache

    def ensure_cache(self) -> None:
        from survivor_identity.face_identification.gallery_builder import (
            build_gallery_cache,
            is_cache_stale,
        )

        if self.rebuild_cache or is_cache_stale(
            self.config.cache_path,
            self.config.gallery_dir,
        ):
            build_gallery_cache(
                gallery_dir=self.config.gallery_dir,
                cache_path=self.config.cache_path,
                model_name=self.config.model_name,
                ctx_id=self.config.ctx_id,
            )

    def load(self) -> tuple[list[str], np.ndarray]:
        from survivor_identity.face_identification.gallery_builder import load_gallery_cache

        self.ensure_cache()
        return load_gallery_cache(self.config.cache_path)

    @property
    def gallery_version(self) -> str:
        if not os.path.isfile(self.config.cache_path):
            return "uncached"
        mtime = int(os.path.getmtime(self.config.cache_path))
        return f"{os.path.basename(self.config.cache_path)}:{mtime}"
