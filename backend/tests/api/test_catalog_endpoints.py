from sqlalchemy import select

from app.models import Clinic, Service


API_KEY = {"X-API-Key": "example-secret"}


def import_payload(clinic_id, clinic_name, city, services, branch_id=None):
    return {
        "source": "clinic_partner_api",
        "clinic": {
            "external_id": clinic_id,
            "name": clinic_name,
            "city": city,
            "address": f"{city} street 10",
            "phone": "+77001234567",
            "website": f"https://{clinic_id}.example.kz",
        },
        "branch": {
            "external_id": branch_id or f"{clinic_id}_branch",
            "name": "Main branch",
            "city": city,
            "address": f"{city} street 10",
            "phone": "+77001234567",
        },
        "services": services,
    }


def service(external_id, name, category, price, updated_at="2026-06-17"):
    return {
        "external_id": external_id,
        "name": name,
        "category": category,
        "price": price,
        "currency": "KZT",
        "updated_at": updated_at,
    }


def seed_catalog_data(client):
    payloads = [
        import_payload(
            "clinic_astana_a",
            "Astana Clinic A",
            "Astana",
            [
                service("srv_mrt_a", "МРТ головного мозга", "МРТ", 25000, "2026-06-17"),
                service("srv_uzi_a", "УЗИ сердца", "УЗИ", 12000, "2026-06-16"),
            ],
        ),
        import_payload(
            "clinic_astana_b",
            "Astana Clinic B",
            "Astana",
            [service("srv_mrt_b", "МРТ головы", "МРТ", 30000, "2026-06-18")],
        ),
        import_payload(
            "clinic_almaty_a",
            "Almaty Clinic A",
            "Almaty",
            [service("srv_kt_a", "КТ грудной клетки", "КТ", 40000, "2026-06-15")],
        ),
    ]
    for item in payloads:
        response = client.post("/api/v1/import/prices", json=item, headers=API_KEY)
        assert response.status_code == 200


def test_list_clinics(client):
    seed_catalog_data(client)

    response = client.get("/api/v1/clinics")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"] == {"limit": 20, "offset": 0, "total": 3}
    first = body["data"][0]
    assert set(first) == {
        "id",
        "name",
        "city",
        "phone",
        "website",
        "branches_count",
        "services_count",
        "last_updated_at",
    }


def test_list_clinics_pagination_and_filters(client):
    seed_catalog_data(client)

    city_response = client.get("/api/v1/clinics", params={"city": "Astana"})
    category_response = client.get("/api/v1/clinics", params={"category": "КТ"})
    q_response = client.get("/api/v1/clinics", params={"q": "Almaty"})
    page_response = client.get("/api/v1/clinics", params={"limit": 1, "offset": 1})

    assert city_response.json()["meta"]["total"] == 2
    assert {item["city"] for item in city_response.json()["data"]} == {"Astana"}
    assert category_response.json()["meta"]["total"] == 1
    assert category_response.json()["data"][0]["name"] == "Almaty Clinic A"
    assert q_response.json()["meta"]["total"] == 1
    assert q_response.json()["data"][0]["name"] == "Almaty Clinic A"
    assert page_response.json()["meta"] == {"limit": 1, "offset": 1, "total": 3}


def test_get_clinic_details(client, db_session):
    seed_catalog_data(client)
    clinic = db_session.scalar(select(Clinic).where(Clinic.name == "Astana Clinic A"))

    response = client.get(f"/api/v1/clinics/{clinic.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == clinic.id
    assert data["name"] == "Astana Clinic A"
    assert len(data["branches"]) == 1
    assert all("freshness_state" in item for item in data["services"])
    assert all("freshness_age_days" in item for item in data["services"])
    assert {item["name"] for item in data["services"]} == {"МРТ головного мозга", "УЗИ сердца"}


def test_get_clinic_not_found(client):
    response = client.get("/api/v1/clinics/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "CLINIC_NOT_FOUND"


def test_get_service_details(client, db_session):
    seed_catalog_data(client)
    service_row = db_session.scalar(select(Service).where(Service.name == "МРТ головного мозга"))

    response = client.get(f"/api/v1/services/{service_row.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == service_row.id
    assert data["normalized_service"]["name"] == "мрт головного мозга"
    assert data["category"]["name"] == "МРТ"
    assert data["stats"] == {
        "min_price": "25000.00",
        "max_price": "25000.00",
        "average_price": "25000.00",
        "count": 1,
    }
    assert data["prices"][0]["clinic_name"] == "Astana Clinic A"
    assert data["prices"][0]["freshness_state"] in {"fresh", "aging", "stale"}
    assert "freshness_age_days" in data["prices"][0]


def test_get_service_not_found(client):
    response = client.get("/api/v1/services/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SERVICE_NOT_FOUND"


def test_list_categories(client):
    seed_catalog_data(client)

    response = client.get("/api/v1/categories")

    assert response.status_code == 200
    categories = {item["name"]: item for item in response.json()["data"]}
    assert categories["МРТ"]["services_count"] == 2
    assert categories["УЗИ"]["services_count"] == 1
    assert categories["КТ"]["services_count"] == 1


def test_list_cities(client):
    seed_catalog_data(client)

    response = client.get("/api/v1/cities")

    assert response.status_code == 200
    cities = {item["name"]: item for item in response.json()["data"]}
    assert cities["Astana"] == {
        "name": "Astana",
        "clinics_count": 2,
        "services_count": 3,
    }
    assert cities["Almaty"] == {
        "name": "Almaty",
        "clinics_count": 1,
        "services_count": 1,
    }
