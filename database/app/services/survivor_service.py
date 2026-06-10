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
            if not input_vector or len(input_vector) != 512:
                print("⚠️ [서비스] 수신된 벡터가 없거나 256차원이 아닙니다.", flush=True)
                return {"error": "512차원의 올바른 벡터가 필요합니다."}, 400

            # 💡 진단 로그: 현재 DB에 face_vector가 채워진 데이터가 몇 개나 있는지 먼저 확인
            from app.models.database import Survivor

            total_vectors = Survivor.query.filter(
                Survivor.face_vector.isnot(None)
            ).count()
            print(
                f"📊 [서비스 DB 진단] 현재 로컬 DB 내 face_vector 보유 생존자 수: {total_vectors}명",
                flush=True,
            )

            vector_str = f"[{','.join(map(str, input_vector))}]"
            result = SurvivorRepository.match_survivor_by_vector(vector_str)

            db.session.commit()

            if result:
                print(f"🎯 [서비스 매칭 결과] 1순위 매칭 후보 탐색 성공!", flush=True)
                print(f"   - 대상자 ID: {result.id}", flush=True)
                print(f"   - 성명: {result.name}", flush=True)
                print(
                    f"   - 계산된 코사인 유사도: {result.similarity:.2f}%", flush=True
                )

                # 유사도 기준점 검사
                if float(result.similarity) < 95.0:
                    print(
                        f"⚠️ [서비스 판단] 유사도({result.similarity:.1f}%)가 임계치(95.0%) 미만이므로 미식별 처리합니다.",
                        flush=True,
                    )
                    return {
                        "matched": False,
                        "message": f"유사도 미달 (최고 유사도: {result.similarity:.1f}%)",
                    }, 200

                print(
                    "✅ [서비스 판단] 신원 확인 완료. 프론트엔드로 매칭 정보 전달",
                    flush=True,
                )
                return {
                    "matched": True,
                    "data": {
                        "id": result.id,
                        "name": result.name,
                        "sex": result.sex,
                        "phone_number": result.phone_number,
                        "similarity": round(float(result.similarity), 2),
                    },
                }, 200
            else:
                print(
                    "❌ [서비스 매칭 결과] DB에서 비교 가능한 대상(face_vector가 Null이 아닌 데이터)을 찾지 못했습니다.",
                    flush=True,
                )
                return {
                    "matched": False,
                    "message": "비교할 부모 벡터 데이터가 없습니다.",
                }, 200

        except Exception as e:
            db.session.rollback()
            print(
                f"🚨 [서비스 예외 발생] 데이터베이스 트랜잭션 오류: {str(e)}",
                flush=True,
            )
            raise e
