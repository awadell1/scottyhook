from os.path import dirname, join
import json
import pytest
import logging
from scottyhook import scottyhook

DIR = dirname(__file__)


@pytest.fixture
def client():
    scottyhook.app.config["SCOTTYHOOK_CONFIG"] = join(DIR, "test_config.yml")
    scottyhook.app_setup()
    with scottyhook.app.test_client() as client:
        yield client


def valid_response():
    with open(join(DIR, "valid_response.json"), "r") as io:
        payload = json.load(io)
    return payload


def test_ping(client):
    resp = client.post("/", headers={"X-GitHub-Event": "ping"})
    assert resp.status_code == 200
    assert resp.json["status"] == "pong"


def test_not_released(client):
    # Ignore if not released
    resp = client.post(
        "/", headers={"X-GitHub-Event": "release"}, json={"action": "created"}
    )
    assert resp.status_code == 200


def test_missing_assets(client):
    # Check error on missing release
    resp = client.post(
        "/", headers={"X-GitHub-Event": "release"}, json={"action": "released"}
    )
    assert resp.status_code == 200


def test_good(client):
    resp = client.post(
        "/", headers={"X-GitHub-Event": "release"}, json=valid_response(),
    )
    assert resp.status_code == 200
