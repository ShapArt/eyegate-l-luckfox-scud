

def test_self_enroll_flow(client):
    # create user
    create = client.post("/api/users/", json={"login": "alice", "pin": "4321"})
    assert create.status_code == 200
    user = create.json()

    # login to get token
    login = client.post("/api/auth/login", json={"login": "alice", "password": "4321"})
    assert login.status_code == 200
    token = login.json()["token"]

    # self-enroll using bearer token
    enroll = client.post(
        "/api/users/me/enroll", headers={"Authorization": f"Bearer {token}"}
    )
    assert enroll.status_code == 200
    enrolled = enroll.json()
    assert enrolled["id"] == user["id"]
    assert enrolled["has_face"] is True

    # validate retrieval
    users = client.get("/api/users/").json()
    assert any(u["id"] == user["id"] and u.get("has_face") for u in users)

    # stored embedding should be present and match zero-vector dummy descriptor
    stored = next(u for u in users if u["id"] == user["id"])
    assert stored["has_face"] is True


def test_admin_enroll_sets_face_embedding(client):
    # create user
    create = client.post("/api/users/", json={"login": "bob", "pin": "9999"})
    assert create.status_code == 200
    user = create.json()

    # admin enroll via capture
    enroll = client.post(f"/api/users/{user['id']}/enroll")
    assert enroll.status_code == 200
    enrolled = enroll.json()
    assert enrolled["has_face"] is True

    users = client.get("/api/users/").json()
    stored = next(u for u in users if u["id"] == user["id"])
    assert stored["has_face"] is True
