"""외부 수집 잡의 키 확인.

키가 비어 있으면 발급처를 부르지 않는다. 빈 키로 부르면 발급처는 모든
요청을 거절하고, 잡은 격자·페이지 수만큼 거절을 받아 가며 경고로 로그를
덮어 진짜 문제를 묻는다. 운영자가 키를 넣지 않은 공급자는 아예 부르지
않는 것이 기본 동작이다 — 외부 API 는 키를 넣은 사람만 쓴다.

스텁 모드 판정(map_project_hub.place_stubs.places_stub_active)과는 따로
본다. 스텁 모드가 꺼져 있고 키도 없으면, 가짜 데이터를 만들지도 않고
발급처를 부르지도 않은 채 건너뛴다.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 경고를 이미 남긴 잡 이름. 주기 잡이 돌 때마다 같은 경고가 쌓이지 않게
# 프로세스마다 한 번만 알린다.
_warned: set[str] = set()


def missing_key(job: str, key: str, env_name: str) -> bool:
    """키가 비었으면 True 를 돌려준다. 잡마다 처음 한 번만 경고를 남긴다.

    job: 로그에 쓸 잡 이름. key: 확인할 키 값(로그에 남기지 않는다).
    env_name: 운영자가 채워야 할 환경변수 이름.
    """
    if key:
        return False
    if job not in _warned:
        _warned.add(job)
        logger.warning(
            "%s skipped — %s 가 비어 있어 발급처를 부르지 않는다", job, env_name
        )
    return True
