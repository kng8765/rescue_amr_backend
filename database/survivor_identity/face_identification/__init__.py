"""생존자 1:N 얼굴 식별 패키지 (InsightFace ArcFace).

head crop → landmark 정렬 → ArcFace embedding → gallery 1:N 매칭.
주요 API: FaceRecognizer
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .recognizer import FaceRecognizer

__all__ = ["FaceRecognizer"]


def __getattr__(name: str):
    if name == "FaceRecognizer":
        from .recognizer import FaceRecognizer

        return FaceRecognizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
