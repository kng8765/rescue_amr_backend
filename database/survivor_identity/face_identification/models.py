"""InsightFace ONNX 모델 로더.

생존자 1:N 매칭 파이프라인에서 사용하는 두 가지 모델을 로드한다.

- Recognition (buffalo_sc / MobileFaceNet): 정렬된 112×112 얼굴 → ArcFace 임베딩
- Landmark (buffalo_l / 2d106det): 크롭 이미지 → 106개 2D 랜드마크

입력은 이미 head crop으로 잘려 있으므로 별도 face detector는 사용하지 않는다.
buffalo_sc에는 landmark 모델이 없어 recognition과 landmark를 서로 다른 pack에서 로드한다.
"""

from __future__ import annotations

import glob
import os.path as osp
from dataclasses import dataclass

from insightface.model_zoo import model_zoo
from insightface.utils import ensure_available

LANDMARK_MODEL_PACK = "buffalo_l"


@dataclass
class InsightFaceModels:
    """InsightFace recognition·landmark ONNX 모델을 묶어 보관하는 컨테이너.

    Attributes:
        recognition: ArcFace 임베딩 추출 모델 (taskname='recognition').
        landmark: 106-point 2D 랜드마크 추론 모델 (taskname='landmark_2d_106').
        model_name: recognition pack 이름 (예: 'buffalo_sc').
    """

    recognition: object
    landmark: object
    model_name: str


def _load_task_model(model_dir: str, taskname: str):
    """모델 디렉터리에서 taskname에 해당하는 ONNX 파일을 탐색해 로드한다."""
    for onnx_file in sorted(glob.glob(osp.join(model_dir, "*.onnx"))):
        model = model_zoo.get_model(onnx_file)
        if model is not None and model.taskname == taskname:
            return model
    return None


def load_models(model_name: str = "buffalo_sc", ctx_id: int = -1) -> InsightFaceModels:
    """Load ArcFace recognition and 106-point landmark models.

    Recognition comes from ``model_name`` (default: buffalo_sc / MobileFaceNet).
    Landmark always comes from ``buffalo_l``'s ``2d106det`` model because
    ``buffalo_sc`` does not ship a landmark model.
    """
    rec_dir = ensure_available("models", model_name, root="~/.insightface")
    landmark_dir = ensure_available("models", LANDMARK_MODEL_PACK, root="~/.insightface")

    recognition = _load_task_model(rec_dir, "recognition")
    landmark = _load_task_model(landmark_dir, "landmark_2d_106")

    if recognition is None or landmark is None:
        raise RuntimeError(
            f"Could not load recognition/landmark models "
            f"(recognition pack='{model_name}', landmark pack='{LANDMARK_MODEL_PACK}'). "
            "Install insightface and ensure model packs downloaded successfully."
        )

    recognition.prepare(ctx_id)
    landmark.prepare(ctx_id)
    return InsightFaceModels(
        recognition=recognition,
        landmark=landmark,
        model_name=model_name,
    )
