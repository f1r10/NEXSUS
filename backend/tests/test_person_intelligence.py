"""Person Intelligence contract: no cross-case leaks, no unsourced attribution."""
from test_api import client, setup, headers, create_case


def make_person(client, csrf, case, name="Şəxs A"):
    r = client.post(f"/api/v1/cases/{case}/entities", headers=headers(csrf),
                    json={"entity_type": "person", "display_name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_account(client, csrf, case, username):
    r = client.post(f"/api/v1/cases/{case}/social/accounts", headers=headers(csrf),
                    json={"platform": "example", "external_id": username, "username": username})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_evidence(client, csrf, case, text="Authorized source snapshot"):
    r = client.post(f"/api/v1/cases/{case}/evidence/text", headers=headers(csrf),
                    json={"title": "Source", "content": text})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_profile_only_approved_identity_and_case_evidence(client):
    csrf = setup(client)
    a, b = create_case(client, csrf, "Case A"), create_case(client, csrf, "Case B")
    person = make_person(client, csrf, a)
    account = make_account(client, csrf, a, "account-one")
    ev = make_evidence(client, csrf, a)
    foreign = make_evidence(client, csrf, b)

    bad = client.post(f"/api/v1/cases/{a}/social/attributions", headers=headers(csrf),
                      json={"account_id": account, "entity_id": person, "evidence_id": foreign})
    assert bad.status_code == 404

    proposed = client.post(f"/api/v1/cases/{a}/social/attributions", headers=headers(csrf),
                           json={"account_id": account, "entity_id": person, "evidence_id": ev})
    assert proposed.status_code == 201, proposed.text
    p = client.get(f"/api/v1/cases/{a}/people/{person}/profile").json()
    assert p["accounts"] == []
    assert len(p["account_candidates"]) == 1
    assert p["data_scope"] == "authorized_case_only"
    assert client.post(f"/api/v1/cases/{a}/social/attributions", headers=headers(csrf),
                       json={"account_id": account, "entity_id": person, "evidence_id": ev}).status_code == 409

    approved = client.post(f"/api/v1/cases/{a}/social/attributions/{proposed.json()['id']}/review",
                           headers=headers(csrf), json={"decision": "approved"})
    assert approved.status_code == 200, approved.text
    p = client.get(f"/api/v1/cases/{a}/people/{person}/profile").json()
    assert len(p["accounts"]) == 1 and p["accounts"][0]["identity_status"] == "confirmed"
    assert p["account_candidates"] == []
    assert client.post(f"/api/v1/cases/{a}/social/attributions/{proposed.json()['id']}/review",
                       headers=headers(csrf), json={"decision": "rejected"}).status_code == 409


def test_posts_comments_deduplicate_and_require_same_case(client):
    csrf = setup(client)
    a, b = create_case(client, csrf, "Case A"), create_case(client, csrf, "Case B")
    account = make_account(client, csrf, a, "poster")
    commenter = make_account(client, csrf, a, "commenter")
    ev = make_evidence(client, csrf, a)
    wrong_account = make_account(client, csrf, b, "other")
    wrong_evidence = make_evidence(client, csrf, b)
    post = {"author_account_id": account, "platform_post_id": "post-42", "content": "A public post",
            "evidence_id": ev}
    assert client.post(f"/api/v1/cases/{a}/social/posts", json={**post, "evidence_id": wrong_evidence},
                       headers=headers(csrf)).status_code == 404
    assert client.post(f"/api/v1/cases/{a}/social/posts", json={**post, "author_account_id": wrong_account},
                       headers=headers(csrf)).status_code == 404
    added = client.post(f"/api/v1/cases/{a}/social/posts", json=post, headers=headers(csrf))
    assert added.status_code == 201, added.text
    assert added.json()["evidence_id"] == ev
    assert client.post(f"/api/v1/cases/{a}/social/posts", json=post,
                       headers=headers(csrf)).status_code == 409
    comment = {"post_id": added.json()["id"], "author_account_id": commenter,
               "platform_comment_id": "comment-1", "content": "A source-backed reply", "evidence_id": ev}
    assert client.post(f"/api/v1/cases/{a}/social/comments", json={**comment,"author_account_id":wrong_account},
                       headers=headers(csrf)).status_code == 404
    response = client.post(f"/api/v1/cases/{a}/social/comments", json=comment, headers=headers(csrf))
    assert response.status_code == 201, response.text
    assert client.post(f"/api/v1/cases/{a}/social/comments", json=comment,
                       headers=headers(csrf)).status_code == 409
    assert len(client.get(f"/api/v1/cases/{a}/social/posts").json()) == 1
    assert len(client.get(f"/api/v1/cases/{a}/social/comments").json()) == 1
    assert client.get(f"/api/v1/cases/{b}/social/posts").json() == []
    assert client.get(f"/api/v1/cases/{b}/social/comments?post_id={added.json()['id']}").status_code == 404


def test_account_snapshot_history_and_cross_case_guard(client):
    csrf = setup(client)
    a, b = create_case(client, csrf, "Case A"), create_case(client, csrf, "Case B")
    acc = make_account(client, csrf, a, "account")
    ev = make_evidence(client, csrf, a)
    snapshot = {"account_id": acc, "evidence_id": ev, "username": "account",
                "display_name": "Original display", "follower_count": 4}
    r = client.post(f"/api/v1/cases/{a}/social/profile-snapshots", json=snapshot, headers=headers(csrf))
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/cases/{a}/social/profile-snapshots", json={**snapshot, "username": "renamed"}, headers=headers(csrf))
    assert r.status_code == 201
    history = client.get(f"/api/v1/cases/{a}/social/accounts/{acc}/profile-snapshots").json()
    assert len(history) == 2
    assert {x["username"] for x in history} == {"account", "renamed"}
    assert client.get(f"/api/v1/cases/{b}/social/accounts/{acc}/profile-snapshots").status_code == 404


def test_social_graph_is_directional_and_never_infers_person_relation(client):
    csrf = setup(client)
    case = create_case(client, csrf)
    person = make_person(client, csrf, case)
    a, b = make_account(client, csrf, case, "a"), make_account(client, csrf, case, "b")
    ev = make_evidence(client, csrf, case)
    proposal = client.post(f"/api/v1/cases/{case}/social/attributions", headers=headers(csrf),
                           json={"account_id": a, "entity_id": person, "evidence_id": ev}).json()
    client.post(f"/api/v1/cases/{case}/social/attributions/{proposal['id']}/review",
                headers=headers(csrf), json={"decision": "approved"})
    client.post(f"/api/v1/cases/{case}/social/follows", headers=headers(csrf),
                json={"follower_id": b, "followed_id": a, "evidence_id": ev})
    graph = client.get(f"/api/v1/cases/{case}/social/graph").json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["source"] == b and graph["edges"][0]["target"] == a
    assert graph["edges"][0]["label"] == "FOLLOWS"
    assert person not in {n["id"] for n in graph["nodes"]}


def test_global_people_search_only_member_cases_and_viewer_cannot_write(client):
    csrf = setup(client)
    a, b = create_case(client, csrf, "Case A"), create_case(client, csrf, "Case B")
    p1 = make_person(client, csrf, a, "Kamran Test")
    p2 = make_person(client, csrf, b, "Kamran Test")
    r = client.post("/api/v1/users", headers=headers(csrf), json={
        "email": "viewer2@example.local", "display_name": "Case Viewer",
        "password": "secure-long-password-abc"})
    assert r.status_code == 201
    assert client.post(f"/api/v1/cases/{a}/members", headers=headers(csrf),
                       json={"email": "viewer2@example.local", "role": "viewer"}).status_code == 201
    client.post("/api/v1/auth/logout", headers=headers(csrf))
    login = client.post("/api/v1/auth/login", json={
        "email": "viewer2@example.local", "password": "secure-long-password-abc"})
    assert login.status_code == 200
    viewer_csrf = login.json()["csrf_token"]
    results = client.get("/api/v1/people/search?q=Kamran").json()
    assert [x["id"] for x in results] == [p1]
    assert p2 not in str(results)
    assert client.get(f"/api/v1/cases/{b}/people/{p2}/profile").status_code == 404
    assert client.post(f"/api/v1/cases/{a}/social/posts", headers=headers(viewer_csrf), json={
        "author_account_id": p1, "platform_post_id":"x", "content":"text", "evidence_id": p1
    }).status_code == 403
    assert client.get("/api/v1/people/search?q=%25%25").json() == []
