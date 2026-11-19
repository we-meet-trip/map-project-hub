"""요청에 실려 온 좌표를 꺼낸다.

좌표는 감싸서 온다(map_project_hub.crypto.location_seal). 여기서는 그 봉투를 열어 값으로
되돌리고, 열 수 없으면 요청을 거절한다.

**값으로 온 좌표는 받지 않는다.** 봉투를 못 열었을 때 평문으로 물러서면,
감싸는 쪽이 조용히 고장 나도 아무도 알아차리지 못한 채 평문이 흐른다. 그
상태는 감싸지 않은 것과 같으면서 감쌌다고 믿게 만든다는 점에서 더 나쁘다.
그래서 봉투 열쇠는 필수이고(부팅 때 확인 — map_project_hub.crypto.location_seal.require_key),
평문 좌표를 받는 길은 두지 않는다.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status

from map_project_hub.crypto.location_seal import SealError, open_seal

logger = logging.getLogger(__name__)

KOREA_LAT = (33.0, 43.0)
KOREA_LNG = (124.0, 132.0)


def _reject(reason: str) -> HTTPException:
    # 사유를 밖으로 자세히 알리지 않는다. 어느 단계에서 막혔는지 알려 주면
    # 그것만으로 무엇을 바꿔 가며 시도할지가 정해진다.
    logger.warning("location seal rejected reason=%s", reason)
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="invalid location"
    )


def _in_korea(lat: float, lng: float) -> bool:
    return KOREA_LAT[0] <= lat <= KOREA_LAT[1] and KOREA_LNG[0] <= lng <= KOREA_LNG[1]


def _opened(request: Request, loc: str | None, fields: tuple[str, ...]) -> dict:
    if loc is None:
        raise _reject("missing sealed location")
    try:
        payload = open_seal(loc)
    except SealError as e:
        raise _reject(str(e)) from e
    values = {}
    for name in fields:
        value = payload.get(name)
        if not isinstance(value, (int, float)):
            raise _reject(f"missing field {name}")
        values[name] = float(value)
    # 좌표를 쓴 사실을 남긴다. 위치 자체는 남기지 않는다 — 기록이 또 하나의
    # 위치 저장소가 되면 감싼 의미가 없다.
    logger.info(
        "location seal opened path=%s caller=%s",
        request.url.path,
        request.client.host if request.client else "unknown",
    )
    return values


def resolve_point(request: Request, loc: str | None) -> tuple[float, float]:
    """한 지점을 꺼낸다."""
    values = _opened(request, loc, ("lat", "lng"))
    lat, lng = values["lat"], values["lng"]
    if not _in_korea(lat, lng):
        raise _reject("out of range")
    return lat, lng


def resolve_pair(
    request: Request, loc: str | None
) -> tuple[float, float, float, float]:
    """출발·도착 두 지점을 꺼낸다."""
    values = _opened(request, loc, ("start_lat", "start_lng", "end_lat", "end_lng"))
    start_lat = values["start_lat"]
    start_lng = values["start_lng"]
    end_lat = values["end_lat"]
    end_lng = values["end_lng"]
    if not _in_korea(start_lat, start_lng) or not _in_korea(end_lat, end_lng):
        raise _reject("out of range")
    return start_lat, start_lng, end_lat, end_lng


def resolve_legs(request: Request, loc: str | None) -> list:
    """경로 요청의 구간 목록을 꺼낸다.

    구간에는 좌표뿐 아니라 장소 이름도 들어간다. 이름만으로도 어디를 다니는지가
    드러나므로 함께 감싸고, 함께 꺼낸다.
    """
    if loc is None:
        raise _reject("missing sealed legs")
    try:
        payload = open_seal(loc)
    except SealError as e:
        raise _reject(str(e)) from e
    legs = payload.get("legs")
    if not isinstance(legs, list):
        raise _reject("sealed legs missing")
    logger.info(
        "location seal opened path=%s caller=%s legs=%d",
        request.url.path,
        request.client.host if request.client else "unknown",
        len(legs),
    )
    if not 1 <= len(legs) <= 20:
        raise _reject("legs out of range")
    return legs


def resolve_polyline(request: Request, loc: str | None) -> list[tuple[float, float]]:
    """경로 폴리라인(2~500 점)을 꺼낸다. 점마다 국내 범위를 다시 본다."""
    if loc is None:
        raise _reject("missing sealed polyline")
    try:
        payload = open_seal(loc)
    except SealError as e:
        raise _reject(str(e)) from e
    raw = payload.get("polyline")
    if not isinstance(raw, list) or not 2 <= len(raw) <= 500:
        raise _reject("polyline out of range")
    points: list[tuple[float, float]] = []
    for point in raw:
        lat = point.get("lat") if isinstance(point, dict) else None
        lng = point.get("lng") if isinstance(point, dict) else None
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lat, lng)):
            raise _reject("polyline point malformed")
        if not _in_korea(lat, lng):
            raise _reject("out of range")
        points.append((float(lat), float(lng)))
    logger.info(
        "location seal opened path=%s caller=%s points=%d",
        request.url.path,
        request.client.host if request.client else "unknown",
        len(points),
    )
    return points


def resolve_origin_and_candidates(
    request: Request, loc: str | None
) -> tuple[dict, list]:
    """반경 필터 요청에서 출발지와 후보를 꺼낸다.

    둘을 한 봉투에 담는 이유는, 따로 담으면 한쪽만 감싸는 실수가 생기고
    그 실수는 나머지 한쪽이 평문으로 흐르는 형태로만 드러나기 때문이다.
    """
    if loc is None:
        raise _reject("missing sealed origin")
    try:
        payload = open_seal(loc)
    except SealError as e:
        raise _reject(str(e)) from e
    opened_origin = payload.get("origin")
    opened_candidates = payload.get("candidates")
    if not isinstance(opened_origin, dict) or not isinstance(opened_candidates, list):
        raise _reject("sealed origin malformed")
    logger.info(
        "location seal opened path=%s caller=%s candidates=%d",
        request.url.path,
        request.client.host if request.client else "unknown",
        len(opened_candidates),
    )
    return opened_origin, opened_candidates
