"""좌표 봉투 열쇠는 필수이고, 평문 좌표를 받는 길은 없다.

세 서비스(user·agent·hub)가 같은 열쇠로 좌표를 감싸 주고받는다. 열쇠가 없으면
hub 는 좌표가 담긴 요청을 하나도 열 수 없으므로 부팅에서 멈춘다. 좌표를 받는
모든 공개 경로는 봉투가 없으면 400 으로 거절한다.
"""
from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from map_project_hub.config import settings
from map_project_hub.crypto.location_seal import require_key
from map_project_hub.routers.hub_routers import router as hub_router
from map_project_hub.routers.rules_router import router as rules_router


@pytest.mark.parametrize(
    "value",
    ["", "not-base64!!", base64.b64encode(b"short-key").decode()],
    ids=["empty", "not-base64", "wrong-length"],
)
def test_require_key_stops_boot_with_generation_hint(monkeypatch, value):
    monkeypatch.setattr(settings, "LOCATION_WIRE_KEY", SecretStr(value))
    with pytest.raises(RuntimeError) as got:
        require_key()
    assert "openssl rand -base64 32" in str(got.value)
    # 열쇠 값은 오류 문구에 남기지 않는다.
    if value:
        assert value not in str(got.value)


def test_require_key_accepts_32_byte_key():
    require_key()  # conftest 의 합성 열쇠


def test_lifespan_refuses_to_start_without_key(monkeypatch):
    import map_project_hub.main as main

    monkeypatch.setattr(settings, "LOCATION_WIRE_KEY", SecretStr(""))
    monkeypatch.setattr(settings, "AUTH_ENFORCED", False)

    async def run():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(RuntimeError, match="MAP_PROJECT_LOCATION_WIRE_KEY"):
        asyncio.run(run())


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(hub_router)
    app.include_router(rules_router)
    return TestClient(app)


PLAIN_GETS = [
    ("/v1/weather/now", {"lat": 37.5, "lng": 127.0}),
    ("/v1/places/nearby", {"lat": 37.5, "lng": 127.0, "category": "cafe"}),
    ("/v1/places/photos", {"lat": 37.5, "lng": 127.0, "query": "장소"}),
    ("/v1/transit/subway", {"start_lat": 37.5, "start_lng": 127.0, "end_lat": 37.6, "end_lng": 127.1}),
    ("/v1/transit/routes", {"start_lat": 37.5, "start_lng": 127.0, "end_lat": 37.6, "end_lng": 127.1}),
    ("/v1/mobility/bike-stations", {"lat": 37.5, "lng": 127.0}),
    ("/v1/mobility/pm-vehicles", {"lat": 37.5, "lng": 127.0}),
]


@pytest.mark.parametrize("path,params", PLAIN_GETS, ids=[p for p, _ in PLAIN_GETS])
def test_plain_coordinates_are_rejected(path, params, stub_mode):
    assert _client().get(path, params=params).status_code == 400


@pytest.mark.parametrize(
    "path,body",
    [
        ("/v1/directions/batch", {"mode": "walk", "legs": [{
            "start_lat": 37.5, "start_lng": 127.0, "goal_lat": 37.6, "goal_lng": 127.1,
            "start_name": "가", "goal_name": "나"}]}),
        ("/v1/rules/filter/mobility-radius", {
            "mobility": "foot", "origin": {"lat": 37.5, "lng": 127.0},
            "candidates": [{"content_id": "a", "lat": 37.5, "lng": 127.0}]}),
    ],
    ids=["directions", "mobility-radius"],
)
def test_plain_coordinate_bodies_are_rejected(path, body, stub_mode):
    assert _client().post(path, json=body).status_code == 400
