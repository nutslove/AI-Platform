import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.store.memory import store


@pytest.fixture(autouse=True)
def fresh_store():
    """各テストごとにストアをシード状態へリセットする。"""
    store.reset()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
