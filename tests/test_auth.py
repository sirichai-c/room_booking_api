def test_register_returns_user_without_password(client):
    res = client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    assert res.status_code == 201
    assert res.json() == {"id": 1, "username": "carol", "is_admin": False}


def test_register_duplicate_username(client):
    body = {"username": "carol", "password": "secret-pass"}
    client.post("/auth/register", json=body)
    res = client.post("/auth/register", json=body)
    assert res.status_code == 409


def test_register_validation_error_format(client):
    res = client.post("/auth/register", json={"username": "x", "password": "short"})
    assert res.status_code == 422
    body = res.json()
    assert isinstance(body["detail"], str)
    assert {e["field"] for e in body["errors"]} == {"username", "password"}


def test_login_and_me(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    res = client.post("/auth/token", data={"username": "carol", "password": "secret-pass"})
    assert res.status_code == 200
    token = res.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "carol"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    res = client.post("/auth/token", data={"username": "carol", "password": "wrong-pass"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/auth/token", data={"username": "nobody", "password": "whatever1"})
    assert res.status_code == 401


def test_me_without_token(client):
    res = client.get("/auth/me")
    assert res.status_code == 401
    assert res.headers["www-authenticate"] == "Bearer"


def test_me_with_forged_token(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_old_x_user_header_no_longer_works(client):
    res = client.get("/bookings/me", headers={"X-User": "alice"})
    assert res.status_code == 401


# ---------- username ไม่แยกตัวพิมพ์ ----------

def test_username_is_case_insensitive(client):
    res = client.post("/auth/register", json={"username": "Carol", "password": "secret-pass"})
    assert res.json()["username"] == "carol"
    # สมัครซ้อนด้วยตัวพิมพ์ต่างกันไม่ได้
    assert client.post("/auth/register", json={"username": "CAROL", "password": "secret-pass"}).status_code == 409
    # login ด้วยตัวพิมพ์ไหนก็ได้
    assert client.post("/auth/token", data={"username": "cArOl", "password": "secret-pass"}).status_code == 200


# ---------- กันเดารหัสผ่าน ----------

def _login(client, username, password):
    return client.post("/auth/token", data={"username": username, "password": password})


def test_too_many_failed_logins_are_blocked(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    for _ in range(5):
        assert _login(client, "carol", "wrong-pass").status_code == 401

    res = _login(client, "carol", "secret-pass")  # รหัสถูกก็ยังโดนพัก
    assert res.status_code == 429
    assert int(res.headers["retry-after"]) > 0
    assert isinstance(res.json()["detail"], str)


def test_success_resets_failure_count(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    for _ in range(4):
        _login(client, "carol", "wrong-pass")
    assert _login(client, "carol", "secret-pass").status_code == 200
    for _ in range(4):
        assert _login(client, "carol", "wrong-pass").status_code == 401


def test_block_is_per_username(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret-pass"})
    for _ in range(5):
        _login(client, "dave", "wrong-pass")
    assert _login(client, "dave", "wrong-pass").status_code == 429
    assert _login(client, "carol", "secret-pass").status_code == 200
