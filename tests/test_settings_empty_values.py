"""빈 환경변수는 '설정하지 않음'으로 본다.

실행 구성(compose 등)이 값 없는 변수를 빈 문자열로 넘기는 일이 흔하다. 그때
불리언·숫자 설정이 파싱 오류로 부팅을 깨뜨리지 않고 기본값으로 떨어져야 한다.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from map_project_hub.config import Settings


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("HUB_DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
    return monkeypatch


@pytest.mark.parametrize(
    "name,field,expected",
    [
        ("HUB_PLACES_STUB_MODE", "PLACES_STUB_MODE", False),
        ("HUB_AUTH_ENFORCED", "AUTH_ENFORCED", False),
        ("HUB_KAKAO_CACHE_TTL_SEC", "KAKAO_CACHE_TTL_SEC", 3600),
        ("HUB_ODSAY_REQUEST_TIMEOUT_SEC", "ODSAY_REQUEST_TIMEOUT_SEC", 3.0),
        ("MAP_PROJECT_REDIS_DB_HUB_CACHE", "REDIS_DB_CACHE", 4),
        ("HUB_INTERNAL_TRUSTED_CIDRS", "HUB_INTERNAL_TRUSTED_CIDRS", "172.16.0.0/12,10.0.0.0/8,192.168.0.0/16"),
        ("MAP_PROJECT_REDIS_URL", "REDIS_URL", "redis://redis:6379"),
    ],
)
def test_empty_value_falls_back_to_default(base_env, name, field, expected):
    base_env.setenv(name, "")
    assert getattr(Settings(_env_file=None), field) == expected


def test_non_empty_value_still_applies(base_env):
    base_env.setenv("HUB_PLACES_STUB_MODE", "true")
    base_env.setenv("HUB_KAKAO_CACHE_TTL_SEC", "10")
    s = Settings(_env_file=None)
    assert s.PLACES_STUB_MODE is True and s.KAKAO_CACHE_TTL_SEC == 10


def test_empty_database_url_fails_as_missing(monkeypatch):
    monkeypatch.setenv("HUB_DATABASE_URL", "")
    with pytest.raises(ValidationError) as got:
        Settings(_env_file=None)
    assert [e["type"] for e in got.value.errors()] == ["missing"]
