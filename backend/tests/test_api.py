"""Critical vertical-slice contract/security regression tests."""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base, get_db
from app.main import app
from app import models  # noqa: F401

BOOT = "an-example-bootstrap-token-with-more-than-32-characters"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("NEXUS_BOOTSTRAP_TOKEN", BOOT)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    local = sessionmaker(bind=engine, expire_on_commit=False)
    def override():
        with local() as db:
            yield db
    app.dependency_overrides[get_db] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def setup(client):
    response = client.post("/api/v1/auth/bootstrap", headers={"X-Bootstrap-Token": BOOT}, json={
        "email": "admin@example.local", "display_name": "Administrator", "password": "long-secure-password-123",
    })
    assert response.status_code == 201, response.text
    return response.json()["csrf_token"]


def headers(csrf):
    return {"X-CSRF-Token": csrf}


def create_case(client, csrf, name="Case Alpha"):
    w = client.post("/api/v1/workspaces", json={"name": "Investigation"}, headers=headers(csrf))
    assert w.status_code == 201, w.text
    c = client.post(f"/api/v1/workspaces/{w.json()['id']}/cases", json={"name": name}, headers=headers(csrf))
    assert c.status_code == 201, c.text
    return c.json()["id"]


def test_health_and_bootstrap_is_one_time(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.get("/api/v1/auth/setup-required").json()["required"]
    setup(client)
    assert not client.get("/api/v1/auth/setup-required").json()["required"]
    r = client.post("/api/v1/auth/bootstrap", headers={"X-Bootstrap-Token": BOOT},
                    json={"email": "second@example.local", "display_name": "Second", "password": "long-secure-password-123"})
    assert r.status_code == 409


def test_csrf_and_authentication(client):
    csrf = setup(client)
    assert client.post("/api/v1/workspaces", json={"name": "No CSRF"}).status_code == 403
    assert client.post("/api/v1/workspaces", json={"name": "Valid"}, headers=headers(csrf)).status_code == 201
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers(csrf)).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_case_isolation_and_role_enforcement(client):
    csrf = setup(client)
    a = create_case(client, csrf, "Case A")
    b = create_case(client, csrf, "Case B")
    create_user = client.post("/api/v1/users", headers=headers(csrf), json={
        "email": "analyst@example.local", "display_name": "Analyst", "password": "long-secure-password-456",
    })
    assert create_user.status_code == 201
    assert client.post(f"/api/v1/cases/{a}/members", headers=headers(csrf), json={
        "email": "analyst@example.local", "role": "viewer"}).status_code == 201
    client.post("/api/v1/auth/logout", headers=headers(csrf))
    login = client.post("/api/v1/auth/login", json={"email": "analyst@example.local", "password": "long-secure-password-456"})
    assert login.status_code == 200
    viewer_csrf = login.json()["csrf_token"]
    assert len(client.get("/api/v1/cases").json()) == 1
    assert client.get(f"/api/v1/cases/{b}/entities").status_code == 404
    assert client.get(f"/api/v1/cases/{a}/entities").status_code == 200
    assert client.post(f"/api/v1/cases/{a}/entities", headers=headers(viewer_csrf), json={
        "entity_type": "person", "display_name": "Test"}).status_code == 403


def test_person_graph_provenance_and_cross_case_rejection(client):
    csrf = setup(client)
    case_a = create_case(client, csrf, "Case A")
    case_b = create_case(client, csrf, "Case B")
    def entity(case, name):
        r = client.post(f"/api/v1/cases/{case}/entities", headers=headers(csrf),
                        json={"entity_type": "person", "display_name": name})
        assert r.status_code == 201, r.text
        return r.json()["id"]
    a = entity(case_a, "Əli Məmmədov")
    b = entity(case_a, "Kamran Əliyev")
    c = entity(case_b, "Other case person")
    evidence = client.post(f"/api/v1/cases/{case_a}/evidence/text", headers=headers(csrf),
                           json={"title": "Sənəd", "content": "İki şəxs eyni tədbirdə qeyd olunub"})
    assert evidence.status_code == 201
    ev = evidence.json()["id"]
    cross = client.post(f"/api/v1/cases/{case_a}/relationships", headers=headers(csrf),
                        json={"source_id": a, "target_id": c, "relation_type": "KNOWS"})
    assert cross.status_code == 404
    new = client.post(f"/api/v1/cases/{case_a}/relationships", headers=headers(csrf),
                      json={"source_id": a, "target_id": b, "relation_type": "AT_EVENT", "evidence_id": ev})
    assert new.status_code == 201, new.text
    assert new.json()["review_status"] == "proposed"
    approve = client.post(f"/api/v1/cases/{case_a}/relationships/{new.json()['id']}/review",
                          headers=headers(csrf), json={"decision": "approved"})
    assert approve.status_code == 200, approve.text
    graph = client.get(f"/api/v1/cases/{case_a}/graph").json()
    assert len(graph["nodes"]) == 2 and len(graph["edges"]) == 1
    assert graph["edges"][0]["status"] == "approved"
    assert len(client.get(f"/api/v1/cases/{case_a}/evidence?q=şəxs").json()) == 1
    assert len(client.get(f"/api/v1/cases/{case_b}/graph").json()["nodes"]) == 1


def test_social_follow_requires_case_scoped_evidence(client):
    csrf = setup(client)
    case = create_case(client, csrf)
    another = create_case(client, csrf, "Another")
    def account(case_id, name):
        r = client.post(f"/api/v1/cases/{case_id}/social/accounts", headers=headers(csrf),
                        json={"platform": "example", "external_id": name, "username": name})
        assert r.status_code == 201, r.text
        return r.json()["id"]
    a = account(case, "a")
    b = account(case, "b")
    other = account(another, "c")
    ev = client.post(f"/api/v1/cases/{case}/evidence/text", headers=headers(csrf),
                     json={"title": "API snapshot", "content": "example account b follows a"}).json()["id"]
    invalid = client.post(f"/api/v1/cases/{case}/social/follows", headers=headers(csrf),
                          json={"follower_id": other, "followed_id": a, "evidence_id": ev})
    assert invalid.status_code == 404
    valid = client.post(f"/api/v1/cases/{case}/social/follows", headers=headers(csrf),
                        json={"follower_id": b, "followed_id": a, "evidence_id": ev})
    assert valid.status_code == 201, valid.text
    assert len(client.get(f"/api/v1/cases/{case}/social/follows").json()) == 1
    assert client.get(f"/api/v1/cases/{another}/social/follows").json() == []


def test_no_external_transform_registered(client):
    csrf = setup(client)
    case = create_case(client, csrf)
    entity = client.post(f"/api/v1/cases/{case}/entities", headers=headers(csrf),
                         json={"entity_type": "person", "display_name": "Test"}).json()["id"]
    transforms = client.get(f"/api/v1/cases/{case}/transforms").json()
    assert len(transforms) == 1 and transforms[0]["network_access"] is False
    forbidden = client.post(f"/api/v1/cases/{case}/transforms", headers=headers(csrf),
                            json={"transform_name": "social.followers.fetch", "input_entity_id": entity})
    assert forbidden.status_code == 422
    local = client.post(f"/api/v1/cases/{case}/transforms", headers=headers(csrf),
                        json={"transform_name": "graph.neighbors", "input_entity_id": entity})
    assert local.status_code == 201 and local.json()["status"] == "succeeded"
