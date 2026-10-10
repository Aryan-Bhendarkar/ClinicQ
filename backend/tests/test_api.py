SLOT = "2030-01-15T10:00:00+00:00"


def book(client, **overrides):
    body = {"patient_name": "Priya Sharma", "doctor_id": 1, "scheduled_at": SLOT, "reason": "Checkup"}
    body.update(overrides)
    return client.post("/api/appointments", json=body)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "OK"}


def test_ready_checks_database(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "READY"


def test_metrics_exposed_in_prometheus_format(client):
    client.get("/api/doctors")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
    assert "clinicq_appointments_booked_total" in r.text


def test_list_doctors(client):
    r = client.get("/api/doctors")
    assert r.status_code == 200
    assert r.json()[0]["name"] == "Dr. Test"


def test_create_doctor(client):
    r = client.post("/api/doctors", json={"name": "Dr. New", "specialty": "Neurology"})
    assert r.status_code == 201
    assert r.json()["id"] > 1


def test_create_appointment(client):
    r = book(client)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "scheduled"
    assert data["doctor"]["name"] == "Dr. Test"


def test_double_booking_rejected(client):
    assert book(client).status_code == 201
    r = book(client, patient_name="Someone Else")
    assert r.status_code == 409


def test_unknown_doctor_rejected(client):
    assert book(client, doctor_id=999).status_code == 422


def test_invalid_payload_rejected(client):
    assert book(client, patient_name="x").status_code == 422


def test_get_and_list_appointments(client):
    appt_id = book(client).json()["id"]
    assert client.get(f"/api/appointments/{appt_id}").json()["patient_name"] == "Priya Sharma"
    assert len(client.get("/api/appointments").json()) == 1
    assert client.get("/api/appointments/9999").status_code == 404


def test_update_status_and_filter(client):
    appt_id = book(client).json()["id"]
    r = client.put(f"/api/appointments/{appt_id}", json={"status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"
    assert len(client.get("/api/appointments", params={"status": "completed"}).json()) == 1
    assert client.get("/api/appointments", params={"status": "scheduled"}).json() == []


def test_cancelled_slot_can_be_rebooked(client):
    appt_id = book(client).json()["id"]
    client.put(f"/api/appointments/{appt_id}", json={"status": "cancelled"})
    assert book(client, patient_name="Next Patient").status_code == 201


def test_delete_appointment(client):
    appt_id = book(client).json()["id"]
    assert client.delete(f"/api/appointments/{appt_id}").status_code == 204
    assert client.get(f"/api/appointments/{appt_id}").status_code == 404


def test_stats(client):
    book(client)
    book(client, scheduled_at="2030-01-15T11:00:00+00:00")
    r = client.get("/api/appointments/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["scheduled"] == 2
    assert body["doctors"] == 1


def test_cannot_delete_doctor_with_appointments(client):
    book(client)
    assert client.delete("/api/doctors/1").status_code == 409
