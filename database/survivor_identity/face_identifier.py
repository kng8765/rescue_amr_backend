"""High-level identity API for head, body, and face crop images."""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import cv2

from survivor_identity.gallery_store import GalleryStore, IdentityConfig
from survivor_identity.matcher import CosineMatcher

LANDMARK_MODEL_PACK = "buffalo_l"


@dataclass(frozen=True)
class IdentityInput:
    image_path: str
    input_id: str
    input_kind: str
    parent_detection_id: str = ""


@dataclass(frozen=True)
class IdentityResult:
    identity_result_id: str
    input_id: str
    input_kind: str
    parent_detection_id: str
    person_id: str
    display_name: str
    status: str
    similarity: float
    threshold: float
    model_version: str
    gallery_version: str
    image_path: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.error is None:
            payload.pop("error", None)
        return payload


class FaceIdentifier:
    """Central ArcFace/cosine identity matcher."""

    def __init__(self, config: IdentityConfig, *, rebuild_cache: bool = False) -> None:
        from survivor_identity.face_identification.models import load_models

        self.config = config
        self.model_version = (
            f"arcface:{config.model_name}+landmark:{LANDMARK_MODEL_PACK}"
        )
        self.models = load_models(model_name=config.model_name, ctx_id=config.ctx_id)
        self.gallery = GalleryStore(config, rebuild_cache=rebuild_cache)
        labels, templates = self.gallery.load()
        self.matcher = CosineMatcher(
            labels,
            templates,
            threshold=config.threshold,
            model_version=self.model_version,
            gallery_version=self.gallery.gallery_version,
        )

    def identify_path(
        self,
        image_path: str,
        *,
        input_id: str | None = None,
        input_kind: str | None = None,
        parent_detection_id: str = "",
    ) -> IdentityResult:
        identity_input = IdentityInput(
            image_path=os.path.abspath(image_path),
            input_id=input_id or self._input_id_from_path(image_path),
            input_kind=input_kind or self._kind_from_path(image_path),
            parent_detection_id=parent_detection_id,
        )
        return self.identify(identity_input)

    def identify(self, identity_input: IdentityInput) -> IdentityResult:
        from survivor_identity.face_identification.embedding import embed_image

        image = cv2.imread(identity_input.image_path)
        if image is None:
            return self._error_result(identity_input, "image_read_failed")

        embedding = embed_image(
            image,
            self.models.recognition,
            self.models.landmark,
        )
        if embedding is None:
            return self._error_result(identity_input, "alignment_failed")

        match = self.matcher.match(embedding)
        return IdentityResult(
            identity_result_id=self._result_id(),
            input_id=identity_input.input_id,
            input_kind=identity_input.input_kind,
            parent_detection_id=identity_input.parent_detection_id,
            person_id=match.person_id,
            display_name=match.display_name,
            status=match.status,
            similarity=match.similarity,
            threshold=match.threshold,
            model_version=match.model_version,
            gallery_version=match.gallery_version,
            image_path=identity_input.image_path,
        )

    def _error_result(self, identity_input: IdentityInput, error: str) -> IdentityResult:
        return IdentityResult(
            identity_result_id=self._result_id(),
            input_id=identity_input.input_id,
            input_kind=identity_input.input_kind,
            parent_detection_id=identity_input.parent_detection_id,
            person_id="unknown",
            display_name="unknown",
            status="unknown",
            similarity=0.0,
            threshold=self.config.threshold,
            model_version=self.model_version,
            gallery_version=self.gallery.gallery_version,
            image_path=identity_input.image_path,
            error=error,
        )

    @staticmethod
    def _result_id() -> str:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"identity_{timestamp}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _input_id_from_path(image_path: str) -> str:
        return os.path.splitext(os.path.basename(image_path))[0]

    @staticmethod
    def _kind_from_path(image_path: str) -> str:
        stem = os.path.splitext(os.path.basename(image_path))[0].lower()
        if stem.endswith("_head") or "_head_" in stem:
            return "head"
        if stem.endswith("_body") or "_body_" in stem:
            return "body"
        if stem.startswith("face_") or "_face" in stem:
            return "face"
        return "crop"
