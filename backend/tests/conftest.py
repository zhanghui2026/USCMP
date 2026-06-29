"""Shared fixtures for backend test suite."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.scripts.mock_data_generator import MockDataGenerator


@pytest.fixture(scope="module")
def mock_data():
    gen = MockDataGenerator()
    gen.generate_all()
    return gen


@pytest.fixture(scope="module")
def client(mock_data):
    from app.main import app
    with TestClient(app) as c:
        yield c
