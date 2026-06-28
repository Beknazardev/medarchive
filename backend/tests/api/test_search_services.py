import pytest


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


def service(external_id, name, category, price, updated_at="2026-06-17", parsed_at=None):
    item = {
        "external_id": external_id,
        "name": name,
        "category": category,
        "price": price,
        "currency": "KZT",
        "updated_at": updated_at,
    }
    if parsed_at is not None:
        item["parsed_at"] = parsed_at
    return item


def seed_search_data(client):
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
            [
                service("srv_mrt_b", "МРТ головы", "МРТ", 30000, "2026-06-18"),
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
    for item in payloads:
        response = client.post("/api/v1/import/prices", json=item, headers=API_KEY)
        assert response.status_code == 200


def search(client, **params):
    return client.get("/api/v1/services/search", params=params)


def test_search_by_q(client):
    seed_search_data(client)

    response = search(client, q="мрт")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 3
    assert all("МРТ" in item["service_name"] for item in body["data"])
    assert all("source_url" in item["price"] for item in body["data"])
    assert all("parsed_at" in item["price"] for item in body["data"])
    assert all("freshness_state" in item["price"] for item in body["data"])
    assert all("freshness_age_days" in item["price"] for item in body["data"])


def test_search_marks_stale_prices(client):
    payload = import_payload(
        "clinic_stale_a",
        "Stale Clinic A",
        "Astana",
        [
            service(
                "srv_stale_mrt",
                "мрт сустава",
                "мрт",
                18000,
                "2026-01-01",
                "2026-05-01T00:00:00Z",
            )
        ],
    )
    response = client.post("/api/v1/import/prices", json=payload, headers=API_KEY)
    assert response.status_code == 200

    response = search(client, q="мрт")
    assert response.status_code == 200
    body = response.json()

    assert body["data"][0]["price"]["freshness_state"] == "stale"
    assert body["data"][0]["price"]["freshness_age_days"] > 30


def test_city_filter(client):
    seed_search_data(client)

    response = search(client, q="мрт", city="Astana")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 2
    assert {item["branch"]["city"] for item in body["data"]} == {"Astana"}


def test_category_filter(client):
    seed_search_data(client)

    response = search(client, q="сердца", category="УЗИ")

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["category"] == "УЗИ"


def test_min_price_max_price_filters(client):
    seed_search_data(client)

    response = search(client, q="мрт", min_price=26000, max_price=35000)

    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["price"]["amount"] in ["30000.00", "30000"]


def test_pagination(client):
    seed_search_data(client)

    first = search(client, q="мрт", sort="price_asc", limit=1, offset=0).json()
    second = search(client, q="мрт", sort="price_asc", limit=1, offset=1).json()

    assert first["meta"] == {"limit": 1, "offset": 0, "total": 3}
    assert second["meta"] == {"limit": 1, "offset": 1, "total": 3}
    assert first["data"][0]["service_id"] != second["data"][0]["service_id"]


def test_sorting(client):
    seed_search_data(client)

    price_asc = search(client, q="мрт", sort="price_asc").json()["data"]
    price_desc = search(client, q="мрт", sort="price_desc").json()["data"]
    updated_desc = search(client, q="мрт", sort="updated_desc").json()["data"]

    assert [item["price"]["amount"] for item in price_asc] == ["25000.00", "30000.00", "40000.00"]
    assert [item["price"]["amount"] for item in price_desc] == ["40000.00", "30000.00", "25000.00"]
    assert updated_desc[0]["price"]["updated_at"] == "2026-06-18"


def test_empty_result(client):
    seed_search_data(client)

    response = search(client, q="стоматология")

    assert response.status_code == 200
    assert response.json() == {"data": [], "meta": {"limit": 20, "offset": 0, "total": 0}}


@pytest.mark.parametrize(
    ("query", "service_name"),
    [
        ("PCR", "ПЦР диагностика"),
        ("ultrasound", "УЗИ сердца"),
        ("MRI", "МРТ головного мозга"),
        ("therapist", "Прием терапевта"),
        ("қан талдауы", "Общий анализ крови"),
    ],
)
def test_search_expands_multilingual_service_aliases(client, query, service_name):
    payload = import_payload(
        f"clinic_alias_{query}",
        "Alias Clinic",
        "Astana",
        [service(f"service_alias_{query}", service_name, "Диагностика", 10000)],
    )
    assert client.post("/api/v1/import/prices", json=payload, headers=API_KEY).status_code == 200

    response = search(client, q=query)

    assert response.status_code == 200
    assert service_name in {item["service_name"] for item in response.json()["data"]}
