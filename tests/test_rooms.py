from conftest import DAY, book


def test_list_rooms_is_public(client):
    res = client.get("/rooms")
    assert res.status_code == 200
    assert [r["name"] for r in res.json()] == ["Room A", "Room B", "Room C"]


def test_filter_rooms(client):
    assert [r["name"] for r in client.get("/rooms?min_capacity=10").json()] == ["Room A"]
    assert [r["name"] for r in client.get("/rooms?name=b").json()] == ["Room B"]


def test_negative_min_capacity(client):
    res = client.get("/rooms?min_capacity=-1")
    assert res.status_code == 422
    assert res.json()["errors"][0]["field"] == "min_capacity"


def test_get_room_404(client):
    assert client.get("/rooms/99").status_code == 404


# ---------- สิทธิ์แอดมิน ----------

def test_create_room_requires_login(client):
    assert client.post("/rooms", json={"name": "Room D", "capacity": 5}).status_code == 401


def test_normal_user_cannot_manage_rooms(client, alice):
    assert client.post("/rooms", json={"name": "Room D", "capacity": 5}, headers=alice).status_code == 403
    assert client.patch("/rooms/1", json={"name": "X"}, headers=alice).status_code == 403
    assert client.delete("/rooms/3", headers=alice).status_code == 403


def test_admin_creates_room(client, admin):
    res = client.post("/rooms", json={"name": "Room D", "capacity": 50}, headers=admin)
    assert res.status_code == 201
    assert res.json() == {"id": 4, "name": "Room D", "capacity": 50}


def test_duplicate_room_name_ignores_case(client, admin):
    res = client.post("/rooms", json={"name": "room a", "capacity": 10}, headers=admin)
    assert res.status_code == 409


def test_rename_to_taken_name(client, admin):
    assert client.patch("/rooms/2", json={"name": "ROOM A"}, headers=admin).status_code == 409
    # เปลี่ยนตัวพิมพ์ชื่อตัวเองได้
    assert client.patch("/rooms/1", json={"name": "ROOM A"}, headers=admin).status_code == 200


def test_cannot_shrink_room_below_booked_attendees(client, admin, alice):
    book(client, alice, room_id=2, attendees=6)
    res = client.patch("/rooms/2", json={"capacity": 5}, headers=admin)
    assert res.status_code == 409
    assert client.patch("/rooms/2", json={"capacity": 6}, headers=admin).status_code == 200


def test_delete_room(client, admin, alice):
    book(client, alice, room_id=1)
    assert client.delete("/rooms/1", headers=admin).status_code == 409
    assert client.delete("/rooms/3", headers=admin).status_code == 204
    assert client.get("/rooms/3").status_code == 404


def test_room_schedule_hides_who_booked(client, alice):
    book(client, alice, room_id=1, start="09:00", end="10:00")
    book(client, alice, room_id=1, start="09:00", end="10:00", day="2099-03-03")

    res = client.get("/rooms/1/bookings")
    assert res.status_code == 200
    assert res.json()[0] == {"start": f"{DAY}T09:00:00+07:00", "end": f"{DAY}T10:00:00+07:00"}

    on_day = client.get(f"/rooms/1/bookings?date={DAY}").json()
    assert len(on_day) == 1
