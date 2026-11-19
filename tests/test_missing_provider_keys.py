"""키가 비어 있으면 외부 수집 잡이 발급처를 부르지 않는다.

스텁 모드가 꺼져 있고 키도 비어 있을 때가 대상이다. 이때 잡은 가짜 데이터를
만들지도, 빈 키로 발급처를 부르지도 않고 건너뛴다. 경고는 잡마다 한 번만 남긴다.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
import pytest
from pydantic import SecretStr

from map_project_hub.config import settings
from map_project_hub.scheduler import hub_scheduler, key_guard, places_sync


@pytest.fixture(autouse=True)
def _no_stub_no_keys(monkeypatch):
    monkeypatch.setattr(settings, "PLACES_STUB_MODE", False)
    monkeypatch.setattr(settings, "AIR_POLL_ENABLED", True)
    for name in ("KMA_SERVICE_KEY", "AIRKOREA_SERVICE_KEY", "TOUR_API_SERVICE_KEY"):
        monkeypatch.setattr(settings, name, SecretStr(""))
    monkeypatch.setattr(key_guard, "_warned", set())

    async def _no_network(*_a, **_k):
        raise AssertionError("빈 키로 발급처를 불렀다")

    monkeypatch.setattr(httpx.AsyncClient, "send", _no_network)

    def _no_client(*_a, **_k):
        raise AssertionError("빈 키로 발급처 클라이언트를 만들었다")

    for name in ("KMAClient", "AirKoreaClient"):
        if hasattr(hub_scheduler, name):
            monkeypatch.setattr(hub_scheduler, name, _no_client)
    monkeypatch.setattr(places_sync, "DurunubiClient", _no_client)

    async def _no_db(*_a, **_k):
        raise AssertionError("키 없이 저장소를 읽었다")

    for name in ("load_active_grids", "load_sido_grids", "loaded_short_term_grids",
                 "loaded_mid_land_regs", "loaded_mid_temp_regs", "latest_mid_tm_fc"):
        monkeypatch.setattr(hub_scheduler, name, _no_db)

    async def _no_courses():
        return 0

    monkeypatch.setattr(places_sync, "count_courses", _no_courses)


JOBS = [
    ("short_term polling", lambda: hub_scheduler.short_term_polling_loop()),
    ("mid_term polling", lambda: hub_scheduler.mid_term_polling_loop()),
    ("nowcast polling", lambda: hub_scheduler.nowcast_polling_loop()),
    ("air polling", lambda: hub_scheduler.air_polling_loop()),
    ("durunubi sync", lambda: places_sync.durunubi_sync_loop(force=True)),
]


@pytest.mark.parametrize("job,make", JOBS, ids=[j for j, _ in JOBS])
def test_job_skips_without_key(job, make, caplog):
    caplog.set_level(logging.WARNING, logger=key_guard.__name__)
    asyncio.run(make())
    assert [r for r in caplog.records if r.getMessage().startswith(job + " skipped")]


@pytest.mark.parametrize("job,make", JOBS, ids=[j for j, _ in JOBS])
def test_missing_key_warning_is_logged_once(job, make, caplog):
    caplog.set_level(logging.WARNING, logger=key_guard.__name__)
    asyncio.run(make())
    asyncio.run(make())
    assert len([r for r in caplog.records if r.getMessage().startswith(job + " skipped")]) == 1


def test_key_value_is_never_logged(caplog):
    caplog.set_level(logging.WARNING, logger=key_guard.__name__)
    assert key_guard.missing_key("probe", "", "SOME_KEY")
    assert not key_guard.missing_key("probe2", "secret-value", "SOME_KEY")
    assert "secret-value" not in caplog.text
