API_KEY = {"X-API-Key": "example-secret"}


def import_payload():
    return {
        "source": "clinic_partner_api",
        "clinic": {
            "external_id": "clinic_search_edge",
            "name": "Search Edge Clinic",
            "city": "Astana",
            "address": "Search street 10",
        },
        "branch": {
            "external_id": "branch_search_edge",
            "name": "Main branch",
            "city": "Astana",
            "address": "Search street 10",
        },
        "services": [
            {
                "external_id": "srv_search_edge",
                "name": "MRI Brain Advanced",
                "category": "Diagnostics",
                "price": 25000,
                "currency": "KZT",
                "updated_at": "2026-06-17",
            }
        ],
    }


def seed_data(client):
    response = client.post("/api/v1/import/prices", json=import_payload(), headers=API_KEY)
    assert response.status_code == 200


def test_search_query_is_case_insensitive(client):
    seed_data(client)

    response = client.get("/api/v1/services/search", params={"q": "MRI"})

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_search_query_trims_extra_spaces(client):
    seed_data(client)

    response = client.get("/api/v1/services/search", params={"q": "  MRI   Brain  "})

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1


def test_search_invalid_pagination_returns_validation_error(client):
    response = client.get("/api/v1/services/search", params={"q": "MRI", "limit": 0, "offset": -1})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
