# app — hub-service 의 최상위 애플리케이션 패키지.
#
# 본 패키지는 다음 하위 모듈로 구성된다:
#   map_project_hub.main           — FastAPI 진입점 + lifespan (스케줄러/DB 라이프사이클)
#   map_project_hub.config         — 환경변수 → Settings 매핑
#   map_project_hub.routers.*      — 외부/내부 HTTP 엔드포인트
#   map_project_hub.db.*           — 비동기 RDB 세션 / forecast 테이블 read/upsert
#   map_project_hub.clients.*      — KMA / Kakao / Naver 외부 API 클라이언트
#   map_project_hub.scheduler.*    — APScheduler cron job + 폴링 루프
#   map_project_hub.cache.*        — L1(Redis) / L2(RDB) 캐시 어댑터
#   map_project_hub.utils.*        — KMA 격자 좌표 변환 등 순수 유틸
#   map_project_hub.schemas.*      — 응답 Pydantic 모델
#   map_project_hub.codes.*        — KMA 카테고리 코드 상수
#
# 파일 자체는 패키지 마커로만 동작하며 export 는 없다.
