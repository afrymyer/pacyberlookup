"""Tests for the voting recommendations app."""

import json
import pytest

from pacyberlookup.voting.app import create_app
from pacyberlookup.voting.models import Recommendation, Vote


@pytest.fixture
def client():
    """Create a test client with an in-memory database."""
    app = create_app(database_url="sqlite:///:memory:")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_list_empty(client):
    """No recommendations initially."""
    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_recommendation(client):
    """Create a recommendation via API."""
    resp = client.post("/api/recommendations", json={
        "title": "Upgrade firewall firmware",
        "description": "Current firmware is 2 versions behind",
        "category": "Infrastructure",
        "priority": "High",
        "submitted_by": "Alice",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Upgrade firewall firmware"
    assert data["id"] == 1


def test_create_missing_fields(client):
    """Reject recommendation without required fields."""
    resp = client.post("/api/recommendations", json={"title": "No desc"})
    assert resp.status_code == 400


def test_cast_vote_approve(client):
    """Vote approve on a recommendation."""
    client.post("/api/recommendations", json={
        "title": "Test rec",
        "description": "Test desc",
    })
    resp = client.post("/api/recommendations/1/vote", json={
        "vote": "approve",
        "voter_name": "Bob",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["approve_count"] == 1
    assert data["reject_count"] == 0


def test_cast_vote_reject(client):
    """Vote reject on a recommendation."""
    client.post("/api/recommendations", json={
        "title": "Test rec",
        "description": "Test desc",
    })
    resp = client.post("/api/recommendations/1/vote", json={
        "vote": "reject",
        "voter_name": "Carol",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reject_count"] == 1


def test_vote_updates_existing(client):
    """Changing vote updates rather than duplicates."""
    client.post("/api/recommendations", json={
        "title": "Test rec",
        "description": "Test desc",
    })
    client.post("/api/recommendations/1/vote", json={
        "vote": "approve",
        "voter_name": "Dave",
    })
    # Change vote
    resp = client.post("/api/recommendations/1/vote", json={
        "vote": "reject",
        "voter_name": "Dave",
    })
    data = resp.get_json()
    assert data["approve_count"] == 0
    assert data["reject_count"] == 1
    assert data["total_votes"] == 1


def test_invalid_vote(client):
    """Reject invalid vote values."""
    client.post("/api/recommendations", json={
        "title": "Test rec",
        "description": "Test desc",
    })
    resp = client.post("/api/recommendations/1/vote", json={
        "vote": "maybe",
    })
    assert resp.status_code == 400


def test_vote_nonexistent(client):
    """Vote on nonexistent recommendation returns 404."""
    resp = client.post("/api/recommendations/999/vote", json={
        "vote": "approve",
    })
    assert resp.status_code == 404


def test_update_status(client):
    """Update recommendation status."""
    client.post("/api/recommendations", json={
        "title": "Test rec",
        "description": "Test desc",
    })
    resp = client.patch("/api/recommendations/1/status", json={
        "status": "Approved",
    })
    assert resp.status_code == 200

    # Verify
    recs = client.get("/api/recommendations").get_json()
    assert recs[0]["status"] == "Approved"


def test_filter_by_status(client):
    """Filter recommendations by status."""
    client.post("/api/recommendations", json={
        "title": "Open one",
        "description": "Desc",
    })
    client.post("/api/recommendations", json={
        "title": "Another",
        "description": "Desc",
    })
    client.patch("/api/recommendations/2/status", json={"status": "Approved"})

    open_recs = client.get("/api/recommendations?status=Open").get_json()
    assert len(open_recs) == 1
    assert open_recs[0]["title"] == "Open one"

    approved_recs = client.get("/api/recommendations?status=Approved").get_json()
    assert len(approved_recs) == 1
    assert approved_recs[0]["title"] == "Another"


def test_index_page(client):
    """Main page loads successfully."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Voting Recommendations" in resp.data
