"""시험용 좌표 봉투 도구.

좌표는 봉투로만 오간다. 시험이 엔드포인트를 부를 때도 실제 호출자처럼 좌표를
감싸서 보낸다. 열쇠는 시험 전용 합성 값이며 conftest 가 환경에 넣는다.
"""
from __future__ import annotations

import base64

from map_project_hub.crypto.location_seal import open_seal, seal

KEY = b"map-wire-test-key-0000000000000!"
KEY_B64 = base64.b64encode(KEY).decode()


def sealed(**fields) -> str:
    """주어진 필드를 봉투 하나로 감싼다."""
    return seal(fields)


def opened(token: str) -> dict:
    """응답 봉투를 연다."""
    return open_seal(token)


POINT = ("lat", "lng")
PAIR = ("start_lat", "start_lng", "end_lat", "end_lng")


def seal_params(params: dict, fields: tuple[str, ...] = POINT) -> dict:
    """평문 좌표 필드를 봉투(loc) 하나로 옮긴다. 나머지 파라미터는 그대로 둔다."""
    coords = {k: params[k] for k in fields if k in params}
    rest = {k: v for k, v in params.items() if k not in fields}
    return {**rest, "loc": seal(coords)}
