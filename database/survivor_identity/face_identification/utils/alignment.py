"""랜드마크 기반 얼굴 정렬 (Face Alignment).

알고리즘 흐름:
  1. head crop 이미지 전체를 loose bbox로 설정 (별도 face detector 없음)
  2. InsightFace 2d106det → 106개 2D 랜드마크 추론
  3. 106점 → 5점 축소 (양쪽 눈·코·입꼬리) — ArcFace 정렬 표준 keypoint
  4. similarity transform으로 112×112 canonical face crop 생성

입력: BGR head crop (H×W×3)
출력: 112×112 정렬된 얼굴 이미지 (정렬 실패 시 None)
"""

from __future__ import annotations

import numpy as np
from insightface.app.common import Face
from insightface.utils import face_align


def landmark_106_to_5(lmk106: np.ndarray) -> np.ndarray:
    """106-point 랜드마크를 ArcFace 정렬용 5-point keypoint로 축소한다.

    알고리즘: InsightFace 106점 표준 인덱스에서 눈 윤곽 점군의 centroid를
    좌/우 눈 중심으로 사용하고, 코·입꼬리는 단일 고정 인덱스를 그대로 취한다.
    """
    lmk5 = np.zeros((5, 2), dtype=np.float32)
    # 좌측 눈: 인덱스 33~41 점군의 평균
    lmk5[0] = np.mean(lmk106[33:42], axis=0)
    # 우측 눈: 인덱스 87~95 점군의 평균
    lmk5[1] = np.mean(lmk106[87:96], axis=0)
    # 코 끝, 좌/우 입꼬리
    lmk5[2] = lmk106[86]
    lmk5[3] = lmk106[52]
    lmk5[4] = lmk106[61]
    return lmk5


def full_image_bbox(image_bgr: np.ndarray, margin_ratio: float = 0.02) -> np.ndarray:
    """head crop 전체를 face bbox로 사용한다 (2% margin으로 경계 여유 확보).

    입력이 이미 head crop이므로 detector 없이 전체 이미지를 얼굴 영역으로 간주한다.
    """
    height, width = image_bgr.shape[:2]
    mx = int(width * margin_ratio)
    my = int(height * margin_ratio)
    return np.array(
        [mx, my, max(mx + 1, width - mx), max(my + 1, height - my)],
        dtype=np.float32,
    )


def align_face(
    image_bgr: np.ndarray,
    landmark_model,
    image_size: int = 112,
) -> np.ndarray | None:
    """랜드마크 기반 similarity transform으로 얼굴을 정렬한다.

    알고리즘:
      1) 2d106det 모델로 106개 랜드마크 추론
      2) 106→5 keypoint 축소
      3) face_align.norm_crop()으로 5점을 ArcFace 표준 위치에 맞춰 warp
    """
    if image_bgr is None or image_bgr.size == 0:
        return None

    face = Face(bbox=full_image_bbox(image_bgr))
    # 106-point landmark 추론
    lmk106 = landmark_model.get(image_bgr, face)
    if lmk106 is None or len(lmk106) < 62:
        task_name = getattr(landmark_model, "taskname", "landmark_2d_106")
        stored = getattr(face, task_name, None)
        if stored is None:
            return None
        lmk106 = stored

    kps5 = landmark_106_to_5(np.asarray(lmk106, dtype=np.float32))
    # similarity transform → 112×112 canonical face
    return face_align.norm_crop(image_bgr, kps5, image_size=image_size)
