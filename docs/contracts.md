# 계약

hub 가 다른 서비스에 내주는 HTTP 계약이다. 필드 단위의 정확한 스키마는 실행 중인 서비스의 OpenAPI(`/docs`, `/openapi.json`)가 기준이고, 이 문서는 경로·전송 방식·오류 형식·한도·소유 관계를 정리한다.

## 1. 공통 규칙

- **전송**: HTTP/JSON. 공개 경로는 `/v1/*`, 관리 콘솔 전용은 `/internal/*`.
- **인증**: `/v1/*` 는 `HUB_AUTH_ENFORCED=true` 일 때만 헤더 `X-Internal-Token`(= `MAP_PROJECT_INTERNAL_SERVICE_TOKEN`)을 요구한다. 기본값은 꺼짐(로컬 실행용)이다 — 외부에 열기 전에는 반드시 켠다. `/internal/*` 는 사설 대역에서 온 요청이면서 관리 전용 토큰(`MAP_PROJECT_HUB_ADMIN_INTERNAL_TOKEN`, 일반 토큰과 달라야 함)을 헤더에 실어야 한다.
- **좌표 봉투**: 좌표·위치가 드러나는 값은 모두 쿼리나 본문의 `loc` 하나로 감싸 보낸다. 평문 좌표 인자는 없다. 형식은 `v1.<iv>.<암호문>`(base64url, AES-256-GCM, 추가 인증 데이터 `map|loc|v1`)이고 평문에 발급 시각 `iat` 가 들어간다. 봉투 유효 시간은 300초. 열쇠는 `MAP_PROJECT_LOCATION_WIRE_KEY`(32바이트 base64)로 user·agent·hub 가 같은 값을 쓴다. 
- **실패를 성공으로 꾸미지 않는다**: 공급자 실패·미설정은 빈 목록의 `ok` 로 내지 않는다. 대부분 `200` 에 `status` 로 구분하고, 몇 경로는 `503` 으로 낸다(아래 표).

### 오류 형식

| 코드 | 본문 | 언제 |
|---|---|---|
| 400 | `{"detail": "invalid location"}` | 봉투가 없음·열 수 없음·만료·필드 누락·국내 범위 밖, 봉투 안 구간 형식 오류. 이유를 자세히 알리지 않는다 |
| 400 | `{"detail": "<설명>"}` | 날씨 기간이 거꾸로이거나 모두 과거 |
| 401 | `{"detail": "invalid internal token"}` | `HUB_AUTH_ENFORCED=true` 인데 토큰이 없거나 다름 |
| 403 | `{"detail": "internal access denied"}` | `/internal/*` 의 대역·토큰 검사 실패 |
| 404 | `{"detail": "region not found"}` | 날씨 지역 이름을 찾지 못함 |
| 422 | FastAPI 검증 오류 | 쿼리·본문 형식 오류, 알 수 없는 이동수단, 격자판 밖 좌표(현재 날씨) |
| 503 | `{"detail": ...}` | 장소 병합 조회의 공급자 실패(`retryable` 포함), 주변 장소 공급자 미설정·실패, 금지 구역 저장소 불가 |

## 2. 공개 경로 (`/v1/*`)

| 경로 | 입력 | 출력 | 실패 표시 | 호출하는 서비스 |
|---|---|---|---|---|
| `GET /v1/weather` | `province`·`city`·`date_start`·`date_end`(KST 날짜) | 일별 예보 `daily`, 비어 있는 날 `missing_dates`·`missing_reasons`, 사용한 발표 시각 | 404 지역 없음, 비는 날은 `missing_*` | user, agent |
| `GET /v1/weather/now` | `loc`={lat,lng} | 격자, 지금(`now`)·어제 같은 시각(`yesterday`)·오늘 요약, 미세먼지(`air`) | 없는 항목은 `null` | user |
| `GET /v1/places` | `province`·`city`·`keyword`·`category_group_code`·`mobility`·`size` | `{places, count, sources}` — 출처 `kakao`·`durunubi` | 503 | user, agent |
| `GET /v1/places/address` | `query` | `{addresses, count}` | 빈 목록 | user |
| `GET /v1/places/nearby` | `loc`={lat,lng}, `category`(stay·food·cafe), `radius`(100~20000), `size`(1~15) | **봉투** `{loc}` — 열면 `{places, count, sources, iat}` | 503 | user |
| `GET /v1/reviews` | `query`, `display`, `start`, `sort` | `{query, reviews, count, start}` — 제목·요약·작성자·게시일·원문 링크 | 빈 목록 | user, agent |
| `GET /v1/places/photos` | `query`(1~60자), `loc`={lat,lng} | `{query, photos, count}` — 사진 주소와 저작자 표시(바이트 없음, 주소는 수명이 짧아 저장하지 말 것) | 빈 목록 | user |
| `POST /v1/directions/batch` | `{mode: walk·bicycle·scooter, loc={legs:[{start_lat, start_lng, goal_lat, goal_lng, start_name, goal_name}]}}` 1~20구간 | `{routes}` — 구간과 같은 순서·길이, 각 `path`·`distance_m`·`duration_s`·`source`·`route_profile`·`data_version` | 구간 값 `null`(호출 측 직선 대체) | user |
| `GET /v1/transit/subway` | `loc`={start_lat,start_lng,end_lat,end_lng} | `{status, route}` | `status` | user |
| `GET /v1/transit/routes` | `loc`={start_lat,start_lng,end_lat,end_lng}, `mode`(all·subway·bus) | `{status, routes}` — 후보마다 구간·거리·노선 좌표 토큰(`map_obj`) | `status` | user |
| `POST /v1/transit/routes/lane` | `{map_obj, types}` | `{status, geometries}` — `types` 와 같은 길이 | `unavailable`(앱은 정류장 직선 유지) | user |
| `GET /v1/mobility/bike-stations` | `loc`={lat,lng}, `radius_m` | `{status, stations, count}` | `status` | user |
| `GET /v1/mobility/pm-vehicles` | `loc`={lat,lng}, `radius_m`, `city` | `{status, vehicles, count}` — 일부 사업자만 실패하면 `partial` | `status` | user |
| `POST /v1/rules/filter/mobility-radius` | `{mobility, loc={origin, candidates}}` 후보 최대 100 | `{filtered, radius_m, dropped}` | 422 알 수 없는 이동수단 | agent |
| `POST /v1/rules/score/indoor-bonus` | 장소 목록(실내 여부·기본 점수, 최대 100)과 그 구간 최대 강수 확률 | 가점 적용 점수 | — | agent |
| `POST /v1/rules/filter/forbidden-zones` | `{loc={polyline:[{lat,lng}...]}}` 2~500점 | `{intersects, zones, suggested_detour}`(우회 제안은 항상 `null`) | 400 봉투·점 오류, 503 저장소 불가 | **지금 부르는 서비스 없음**(실제 호출로는 검증되지 않음) |
| `POST /v1/rules/estimate/dwell` | 장소 목록(최대 100) — 분류 코드·코스 소요 시간 | 체류 시간 추정 | — | agent |

## 3. 내부 경로 (`/internal/*`, 관리 콘솔)

| 경로 | 하는 일 |
|---|---|
| `POST /internal/kma/run-now?which=short\|mid\|housekeep` | 예보 수집 또는 정리를 즉시 실행(이미 도는 수집은 중복 실행하지 않음) |
| `PATCH /internal/grids/{grid_id}` | 구독 격자 켜고 끄기 |
| `GET·POST /internal/forbidden-zones`, `GET·PUT·DELETE /internal/forbidden-zones/{zone_id}` | 금지 구역(폴리곤) 관리 |

## 4. 운영 경로

| 경로 | 내용 |
|---|---|
| `GET /health` | 프로세스 생존(항상 무인증) |
| `GET /health/ready` | DB 와 Redis 캐시에 실제로 한 번씩 물어본 결과(꺼 둔 캐시는 `disabled`). 하나라도 끊겼으면 503 |
| `GET /metrics` | Prometheus 지표(스키마 밖, 내부망에서 수집) |

## 5. 길이·값 한도

| 항목 | 한도 |
|---|---|
| 경로 구간 | 1~20개(봉투 안) |
| 금지 구역 판정 폴리라인 | 2~500점(봉투 안) |
| 반경 필터 후보 | 최대 100개 |
| 주변 장소 | 반경 100~20000m, 결과 1~15개 |
| 사진 검색어 | 1~60자 |
| 따릉이·킥보드 반경 | 100~20000m |
| 좌표 | 위도 33~43, 경도 124~132(봉투를 연 뒤 다시 검사) |
| 봉투 | 문자열 최대 8192자(주변 장소), 유효 300초 |

## 6. 소유 관계

- 이 레포가 정의하고 다른 서비스가 따르는 것: 위 경로와 응답 모양, `hub_data` 스키마와 역할(`map_hub_owner`·`map_hub_migrator`·`map_hub_runtime`), 캐시 키 형식(관리 콘솔은 `kakao:places:*`·`naver:blog:*`·`osrm:*` 앞부분으로만 센다), 마이그레이션 실행 모듈 `map_project_hub.db.migrate`.
- 함께 맞추는 것: 좌표 봉투 형식과 추가 인증 데이터 `map|loc|v1`(user·agent 와 같은 값), 공용 환경변수 이름(`MAP_PROJECT_*`, map-project-infra 의 실행 구성이 넘긴다).
- 관리 콘솔은 `hub_data` 를 읽기만 하고, 쓰기는 `/internal/*` 로 맡긴다.
