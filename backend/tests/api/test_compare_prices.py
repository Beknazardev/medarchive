import pytest

from app.models import ClinicServicePrice


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
        },
        "branch": {
            "external_id": branch_id or f"{clinic_id}_branch",
            "name": "Main branch",
            "city": city,
            "address": f"{city} street 10",
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


def seed_compare_data(client):
    payloads = [
        import_payload(
            "clinic_astana_a",
            "Astana Clinic A",
            "Astana",
            [
                service("srv_mrt_a", "МРТ головного мозга", "МРТ", 20000, "2026-06-17"),
                service("srv_uzi_a", "УЗИ сердца", "УЗИ", 12000, "2026-06-16"),
            ],
        ),
        import_payload(
            "clinic_astana_b",
            "Astana Clinic B",
            "Astana",
            [
                service("srv_mrt_b", "МРТ головы", "МРТ", 35000, "2026-06-18"),
            ],
        ),
        import_payload(
            "clinic_almaty_a",
            "Almaty Clinic A",
            "Almaty",
            [
                service("srv_mrt_c", "МРТ позвоночника", "МРТ", 40000, "2026-06-15"),
            ],
        ),
    ]
    imported = []
    for item in payloads:
        response = client.post("/api/v1/import/prices", json=item, headers=API_KEY)
        assert response.status_code == 200
        imported.append(response.json()["data"])
    return imported


def compare(client, **params):
    return client.get("/api/v1/prices/compare", params=params)


def test_compare_by_service_id(client, db_session):
    seed_compare_data(client)
    price = db_session.query(ClinicServicePrice).order_by(ClinicServicePrice.price.asc()).first()

    response = compare(client, service_id=price.service_id)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["query"]["service_id"] == price.service_id
    assert body["stats"]["count"] == 1
    assert body["items"][0]["service_id"] == price.service_id


def test_compare_by_normalized_service_id(client, db_session):
    seed_compare_data(client)
    price = db_session.query(ClinicServicePrice).order_by(ClinicServicePrice.price.asc()).first()

    response = compare(client, normalized_service_id=price.normalized_service_id)

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["query"]["normalized_service_id"] == price.normalized_service_id
    assert body["stats"]["count"] >= 1
    assert all(item["currency"] == "KZT" for item in body["items"])


def test_compare_by_q(client):
    seed_compare_data(client)

    response = compare(client, q="мрт")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["stats"]["count"] == 3
    assert all("МРТ" in item["service_name"] for item in body["items"])
    assert all("source_url" in item for item in body["items"])
    assert all("parsed_at" in item for item in body["items"])
    assert all("freshness_state" in item for item in body["items"])
    assert all("freshness_age_days" in item for item in body["items"])


def test_city_filter(client):
    seed_compare_data(client)

    response = compare(client, q="мрт", city="Astana")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["stats"]["count"] == 2
    assert {item["city"] for item in body["items"]} == {"Astana"}


def test_category_filter(client):
    seed_compare_data(client)

    response = compare(client, q="сердца", category="УЗИ")

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["stats"]["count"] == 1
    assert body["items"][0]["service_name"] == "УЗИ сердца"


def test_sorting_by_price(client):
    seed_compare_data(client)

    asc = compare(client, q="мрт", sort="price_asc").json()["data"]["items"]
    desc = compare(client, q="мрт", sort="price_desc").json()["data"]["items"]
    updated = compare(client, q="мрт", sort="updated_desc").json()["data"]["items"]

    assert [item["price"] for item in asc] == ["20000.00", "35000.00", "40000.00"]
    assert [item["price"] for item in desc] == ["40000.00", "35000.00", "20000.00"]
    assert updated[0]["updated_at"] == "2026-06-18"


def test_stats_correctness(client):
    seed_compare_data(client)

    response = compare(client, q="мрт")

    assert response.status_code == 200
    stats = response.json()["data"]["stats"]
    assert stats == {
        "min_price": "20000.00",
        "max_price": "40000.00",
        "average_price": "31666.67",
        "count": 3,
        "currency": "KZT",
    }


def test_missing_compare_target_error(client):
    response = compare(client)

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "MISSING_COMPARE_TARGET",
            "message": "service_id, normalized_service_id or q is required",
            "details": [],
        }
    }


def test_empty_result(client):
    seed_compare_data(client)

    response = compare(client, q="стоматология")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "query": {
                "service_id": None,
                "normalized_service_id": None,
                "q": "стоматология",
                "city": None,
                "category": None,
            },
            "stats": {
                "min_price": None,
                "max_price": None,
                "average_price": None,
                "count": 0,
                "currency": None,
            },
            "items": [],
        }
    }


@pytest.mark.parametrize(
    ("query", "service_name"),
    [
        ("ПТР", "ПЦР диагностика"),
        ("ultrasonography", "УЗИ сердца"),
        ("magnetic resonance imaging", "МРТ головного мозга"),
        ("дәрігер қабылдауы", "Прием терапевта"),
    ],
)
def test_compare_expands_multilingual_service_aliases(client, query, service_name):
    payload = import_payload(
        f"clinic_compare_alias_{query}",
        "Compare Alias Clinic",
        "Astana",
        [service(f"service_compare_alias_{query}", service_name, "Диагностика", 12000)],
    )
    assert client.post("/api/v1/import/prices", json=payload, headers=API_KEY).status_code == 200

    response = compare(client, q=query)

    assert response.status_code == 200
    assert service_name in {item["service_name"] for item in response.json()["data"]["items"]}
