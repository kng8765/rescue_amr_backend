import uuid
from app.models.database import db, SurvivorLog, IncidentLog
from app.repositories.survivor_repository import SurvivorRepository


class SurvivorService:
    @staticmethod
    def process_survivor_log(data: dict) -> dict:
        """구조 로그 수신 및 대시보드 Incident Log 일원화 비즈니스 로직"""
        try:
            survivor_id = data.get("id")
            if survivor_id in ["Unknown", "UNIDENTIFIED", "", None]:
                survivor_id = None

            # 1. 생존자 실시간 로그 객체 생성 및 Repository 전달
            new_log = SurvivorLog(
                id=survivor_id,
                detected_x=data.get("detected_x"),
                detected_y=data.get("detected_y"),
                similarity=data.get("similarity"),
                robot_id=data.get("robot_id", "robot1"),
                img_path=data.get("img_path"),
            )
            SurvivorRepository.create_survivor_log(new_log)

            # 2. 대시보드 알림 메시지 가공
            if survivor_id:
                survivor = SurvivorRepository.get_survivor_by_id(survivor_id)
                name_str = survivor.name if survivor else survivor_id
                sim_percent = data.get("similarity", 0) * 100
                integrated_msg = f"<span class='highlight'>[생존자 식별]</span> {name_str} 님 포착 (유사도: {sim_percent:.1f}%)"
            else:
                integrated_msg = f"<span class='highlight-warn'>[미식별 대상 감지]</span> 알 수 없는 구조대상자 포착 (X: {data.get('detected_x')}, Y: {data.get('detected_y')})"

            # 3. 통합 인시던트 로그 생성 및 저장
            from app.repositories.rescue_amr_repository import (
                RescueAmrRepository,
            )  # 순환 참조 방지용 내부 임포트

            integrated_log = IncidentLog(
                id=str(uuid.uuid4()),
                robot_id=data.get("robot_id", "robot1"),
                message=integrated_msg,
            )
            RescueAmrRepository.create_log(integrated_log)

            # 4. 최종 커밋
            db.session.commit()
            return {"status": "success", "message": "Log saved successfully"}, 201

        except Exception as e:
            db.session.rollback()
            raise e  # 발생한 에러는 상위 API 계층으로 던져 처리하게 함

    @staticmethod
    def identify_survivor_by_vector(input_vector: list) -> dict:
        try:
            """현장 포착 벡터 매칭 및 결과 데이터 포맷팅 로직"""
            if not input_vector or len(input_vector) != 256:
                return {"error": "256차원의 올바른 벡터가 필요합니다."}, 400

            vector_str = f"[{','.join(map(str, input_vector))}]"
            result = SurvivorRepository.match_survivor_by_vector(vector_str)

            db.session.commit()
            
            if result:
                return {
                    "matched": True,
                    "data": {
                        "id": result.id,
                        "name": result.name,
                        "birth_year": result.birth_year,
                        "sex": result.sex,
                        "phone_number": result.phone_number,
                        "similarity": round(float(result.similarity), 2),
                    },
                }, 200
            else:
                return {
                    "matched": False,
                    "message": "비교할 부모 벡터 데이터가 없습니다.",
                }, 200
            
        except Exception as e:
            db.session.rollback()
            raise e
