"""Cosine matcher shared by all survivor identity entry points."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MatchResult:
    person_id: str
    display_name: str
    status: str
    similarity: float
    threshold: float
    model_version: str
    gallery_version: str


class CosineMatcher:
    """L2-normalized ArcFace embedding matcher."""

    def __init__(
        self,
        labels: list[str],
        templates: np.ndarray,
        *,
        threshold: float,
        model_version: str,
        gallery_version: str,
    ) -> None:
        self.labels = labels
        self.templates = np.asarray(templates, dtype=np.float32)
        self.threshold = float(threshold)
        self.model_version = model_version
        self.gallery_version = gallery_version

    def match(self, embedding: np.ndarray) -> MatchResult:
        if len(self.labels) == 0 or self.templates.size == 0:
            return self._unknown(0.0)

        query = l2_normalize(np.asarray(embedding, dtype=np.float32))
        similarities = self.templates @ query
        best_idx = int(np.argmax(similarities))
        best_sim = float(similarities[best_idx])
        if best_sim < self.threshold:
            return self._unknown(best_sim)

        person_id = self.labels[best_idx]
        return MatchResult(
            person_id=person_id,
            display_name=self._display_name(person_id),
            status="known",
            similarity=round(best_sim, 4),
            threshold=self.threshold,
            model_version=self.model_version,
            gallery_version=self.gallery_version,
        )

    def _unknown(self, similarity: float) -> MatchResult:
        return MatchResult(
            person_id="unknown",
            display_name="unknown",
            status="unknown",
            similarity=round(float(similarity), 4),
            threshold=self.threshold,
            model_version=self.model_version,
            gallery_version=self.gallery_version,
        )

    @staticmethod
    def _display_name(person_id: str) -> str:
        return person_id.replace("_", " ")


def l2_normalize(vector: np.ndarray, eps: float = 1e-10) -> np.ndarray:
    return vector / (np.linalg.norm(vector) + eps)
