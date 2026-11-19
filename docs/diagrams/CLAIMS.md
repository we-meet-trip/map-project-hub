# 다이어그램 근거표

그림의 노드와 엣지마다 근거를 적는다. 교차 검토는 이 표로 한다. 이 레포 근거는 file:line 으로, 다른 레포 근거는 줄 번호가 바뀌어도 찾을 수 있게 파일과 기호(클래스·함수)로 적는다.

## gateway (hub 게이트웨이 구성)

| 그림 | 요소 | 주장 | 근거 file:line | 확인 방법 |
|---|---|---|---|---|
| gateway | 노드 map-project-user (BFF) | 앱 요청을 받아 hub 공개 경로를 부른다 | map-project-user `HubWeatherNowClient`(`src/main/java/map/project/user/weather/HubWeatherNowClient.java`) | user 의 hub 클라이언트에서 `/v1/` 경로 검색 |
| gateway | 노드 map-project-agent (추천) | 추천 중에 hub 의 날씨·장소·후기·규칙 경로를 부른다 | map-project-agent `HubClient`(`map_project_agent/clients/agent_clients.py`), agent `docs/contracts.md` 'hub 로 보내는 요청' | agent 의 hub 클라이언트 읽기 |
| gateway | 노드 map-project-admin (운영 콘솔) | `/internal/*` 로 hub 쓰기를 맡긴다 | map-project-admin `toggle_grid`·`list_forbidden_zones` 등(`map_project_admin/hub_client.py`) | admin hub 클라이언트 읽기 |
| gateway | 노드 /v1/* 공개 경로 | 날씨·장소·후기·사진·경로·대중교통·이동수단 조회 | `map_project_hub/routers/hub_routers.py:502,804` 외 `@router` 선언들 | `app.routes` 목록 출력 |
| gateway | 노드 /v1/rules/* | 반경·실내 가점·금지 구역·체류 | `map_project_hub/routers/rules_router.py:57,93,111,142` | 같은 파일 |
| gateway | 노드 /internal/* | 즉시 수집·구독 격자·금지 구역, 관리 전용 토큰 가드 | `map_project_hub/routers/internal_router.py:71-77,124`, `map_project_hub/routers/internal_admin_router.py:39` | `tests/test_internal_admin.py` |
| gateway | 노드 노선 좌표 조회 (기본 꺼짐) | 플래그가 꺼져 있으면 외부 호출 없이 `unavailable` | `map_project_hub/config.py:216`, `map_project_hub/routers/hub_routers.py:2161` | 기본값 `False` |
| gateway | 노드 스케줄러 | 예보·실황·대기 폴링과 코스 동기화 잡 등록 | `map_project_hub/scheduler/hub_scheduler.py:569,596-638` | `build_scheduler` 읽기 |
| gateway | 노드 Redis | 공급자 응답 캐시 | `map_project_hub/hub_dependencies.py:82`, `map_project_hub/routers/hub_routers.py:973,1011` | `get_place_cache` 사용처 |
| gateway | 노드 PostgreSQL + PostGIS | `hub_data` 적재본 | `migrations/revisions/001_create_tables.py:44-157` | 마이그레이션 |
| gateway | 노드 민간 API (키가 있을 때만) | 카카오·네이버·Google·ODsay 어댑터, 키가 없으면 클라이언트를 만들지 않음 | `map_project_hub/clients/hub_clients.py:130,943,1101,1470`, `map_project_hub/main.py`(공급자 클라이언트 생성 — 키가 비면 `None`) | `tests/test_startup_config.py` |
| gateway | 노드 OSRM | 직접 띄운 인스턴스, 주소가 비면 부르지 않음 | `map_project_hub/clients/hub_clients.py:1329`, `map_project_hub/config.py`(`OSRM_FOOT_BASE_URL` 기본 빈 값) | `.env.example` |
| gateway | 노드 공공 API (키가 있을 때만) | 기상청·에어코리아·두루누비·국토교통부·서울 따릉이 | `map_project_hub/clients/hub_clients.py:355,497,814,1972,2121`, `map_project_hub/scheduler/key_guard.py:23` | `tests/test_missing_provider_keys.py` |
| gateway | 엣지 user → /v1/* (loc 봉투) | 좌표는 봉투로만 받는다 | `map_project_hub/routers/location_params.py:62` | `tests/test_location_wire_required.py` |
| gateway | 엣지 user → 노선 좌표 조회 | user 가 `/v1/transit/routes/lane` 을 부른다 | map-project-user `TransitRouteClient`(`src/main/java/map/project/user/transit/TransitRouteClient.java`) | user 코드 |
| gateway | 엣지 agent → /v1/* (날씨·장소·후기) | agent 가 날씨·장소·후기를 조회한다 | map-project-agent `HubClient.fetch_weather`·`search_places`·`fetch_reviews`(`map_project_agent/clients/agent_clients.py`) | agent 의 hub 클라이언트 읽기 |
| gateway | 엣지 agent → /v1/rules/* (loc 봉투) | 반경 필터 본문은 `{mobility, loc}` | map-project-agent `HubClient.filter_mobility_radius`(`map_project_agent/clients/agent_clients.py`, 100개씩 나눠 보냄), hub `map_project_hub/routers/location_params.py`(`resolve_origin_and_candidates`, 후보 100 상한) | `tests/test_rules.py` |
| gateway | 엣지 admin → /internal/* (관리 전용 토큰) | 일반 토큰으로는 거절된다 | `map_project_hub/routers/internal_router.py:71-77` | `tests/test_internal_admin.py` |
| gateway | 엣지 /v1/* → Redis | 공급자 응답을 키별 TTL 로 캐시 | `map_project_hub/routers/hub_routers.py:973,1011` | 캐시 키 시험 |
| gateway | 엣지 /v1/* → 민간 API | 키가 있는 공급자만 부른다 | `map_project_hub/routers/hub_routers.py`(각 경로의 `get_*_client() is None` 분기) | `tests/test_provider_stub_isolation.py` |
| gateway | 엣지 /v1/* → OSRM | 구간마다 경로 계산 | `map_project_hub/routers/hub_routers.py:1591,1616` | `tests/test_directions.py` |
| gateway | 엣지 /v1/* → PostgreSQL | 날씨는 적재본만 읽고, 장소 조회는 코스를 읽는다 | `map_project_hub/routers/hub_routers.py:577,1095` | `tests/test_weather_now.py`(발급처 송신 차단) |
| gateway | 엣지 노선 좌표 조회 → 민간 API | ODsay 노선 좌표 | `map_project_hub/routers/hub_routers.py:2120` | `tests/test_transit_routes.py` |
| gateway | 엣지 /v1/rules/* → PostgreSQL | 금지 구역 교차 판정 | `map_project_hub/db/rules_repo.py:36` | `tests/test_rules.py` |
| gateway | 엣지 /internal/* → 스케줄러 (즉시 실행) | 예보 수집을 바로 띄운다 | `map_project_hub/routers/internal_router.py:124,152` | `tests/test_internal_guard.py` |
| gateway | 엣지 /internal/* → PostgreSQL | 구독 격자·금지 구역 쓰기 | `map_project_hub/db/admin_ops_repo.py:51,128` | `tests/test_internal_admin.py` |
| gateway | 엣지 스케줄러 → PostgreSQL (적재) | 예보·실황·대기 upsert | `map_project_hub/scheduler/hub_scheduler.py:184,263,348` | 폴링 시험 |
| gateway | 엣지 스케줄러 → 공공 API (수집) | 키가 있을 때만 발급처를 부른다 | `map_project_hub/scheduler/hub_scheduler.py:173,259,335`, `map_project_hub/scheduler/places_sync.py:144` | `tests/test_missing_provider_keys.py` |

## kma-polling (기상청 예보 수집과 조회)

| 그림 | 요소 | 주장 | 근거 file:line | 확인 방법 |
|---|---|---|---|---|
| kma-polling | 띠 수집 시각 | 단기 02·05·…·23시 10분, 중기 06·18시 10분(KST) | `map_project_hub/scheduler/hub_scheduler.py:591-605` | `CronTrigger` 인자 |
| kma-polling | 호출 스케줄러 → 수집 잡 | `short_term_polling_loop` 실행 | `map_project_hub/scheduler/hub_scheduler.py:596` | 같은 파일 |
| kma-polling | 자기 호출 스텁·키 확인 | 스텁 모드면 건너뜀, 키가 비면 한 번 알리고 건너뜀 | `map_project_hub/scheduler/hub_scheduler.py`(`short_term_polling_loop` 머리), `map_project_hub/scheduler/key_guard.py:23` | `tests/test_missing_provider_keys.py` |
| kma-polling | 호출 수집 잡 → PostGIS (격자 조회) | 활성 구독 격자와 이미 적재한 격자를 읽는다 | `map_project_hub/db/forecast_repo.py`(`load_active_grids`, `loaded_short_term_grids`) | 폴링 시험 |
| kma-polling | 호출 수집 잡 → 기상청 | 격자마다 단기예보를 페이지로 받는다 | `map_project_hub/scheduler/hub_scheduler.py:335`, `map_project_hub/clients/hub_clients.py:497` | `tests/test_kma_forecast_contract.py` |
| kma-polling | 자기 호출 페이지 검사 | `totalCount` 일치·행 누락/중복이 어긋나면 그 발표분을 버린다 | `map_project_hub/clients/hub_clients.py:686` | `tests/test_kma_forecast_contract.py` |
| kma-polling | 호출 수집 잡 → PostGIS (upsert) | 단기예보 적재 | `map_project_hub/scheduler/hub_scheduler.py:348` | 같은 파일 |
| kma-polling | 띠·호출 감시 | 매시 25분 단기 재수집(적재된 격자 건너뜀), 매시 20분 중기 발표분 확인 | `map_project_hub/scheduler/hub_scheduler.py:609-627` | 같은 파일 |
| kma-polling | 호출 호출 서비스 → PostGIS (조회) | `GET /v1/weather` 는 같은 광역의 가장 가까운 활성 격자로 적재본을 읽는다 | `map_project_hub/routers/hub_routers.py:502,577`, `map_project_hub/db/forecast_repo.py:107` | `tests/test_grid_selection.py` |
| kma-polling | 응답 일별 예보 + 빈 날 표시 | `daily`, `missing_dates`·`missing_reasons` | `map_project_hub/schemas/hub_schemas.py`(`WeatherResponse`) | OpenAPI 스키마 |

## hub-data-erd (hub_data 스키마)

| 그림 | 요소 | 주장 | 근거 file:line | 확인 방법 |
|---|---|---|---|---|
| hub-data-erd | region_grid | PK `admin_code`, `lv1~lv3`·`nx`·`ny`·`lon`·`lat` | `migrations/revisions/001_create_tables.py:44-56` | 마이그레이션 |
| hub-data-erd | subscribed_grids | PK `grid_id`, `label` UNIQUE, FK `admin_code`, 중기 구역코드, `is_active` | `migrations/revisions/001_create_tables.py:67-82` | 마이그레이션 |
| hub-data-erd | short_term_forecast | PK `nx·ny·fcst_at·category` | `migrations/revisions/001_create_tables.py:96-107` | 마이그레이션 |
| hub-data-erd | mid_land_forecast | PK `reg_id·tm_fc·fcst_day_offset·am_pm` | `migrations/revisions/001_create_tables.py:127-138` | 마이그레이션 |
| hub-data-erd | mid_temp_forecast | PK `reg_id·tm_fc·fcst_day_offset` | `migrations/revisions/001_create_tables.py:157-170` | 마이그레이션 |
| hub-data-erd | weather_nowcast_snapshots | PK `date_kst·hour_kst·nx·ny` | `migrations/revisions/006_create_weather_nowcast_snapshots.py:42-50` | 마이그레이션 |
| hub-data-erd | air_quality_snapshots | PK `sido·station_name·data_time` | `migrations/revisions/010_create_air_quality_snapshots.py:46-53` | 마이그레이션 |
| hub-data-erd | places | PK `content_id`, `source` 는 kakao·durunubi, `geom` Point(4326) | `migrations/revisions/004_create_places.py:43-68` | 마이그레이션 |
| hub-data-erd | forbidden_zones | PK `zone_id`, `zone` Polygon(4326) | `migrations/revisions/005_create_forbidden_zones.py:42-48` | 마이그레이션 |
| hub-data-erd | 실선 subscribed_grids → region_grid | 외래키 `admin_code` | `migrations/revisions/001_create_tables.py:70-71` | `REFERENCES` |
| hub-data-erd | 점선 short_term_forecast → subscribed_grids | 외래키 없이 `nx·ny` 로 맞춰 읽는다 | `map_project_hub/db/forecast_repo.py`(`load_active_grids`, 조회 SQL) | 외래키 없음(`REFERENCES` 1건뿐) |
| hub-data-erd | 점선 mid_land·mid_temp → subscribed_grids | 외래키 없이 `reg_id` 로 맞춘다 | 같은 파일(중기 적재·조회) | 같음 |
| hub-data-erd | 점선 weather_nowcast_snapshots → subscribed_grids | 시도 대표 구독 격자(`label` 에 공백 없는 행)의 `nx·ny` | `map_project_hub/db/forecast_repo.py:210-220` | `_SIDO_GRIDS_SQL` |
