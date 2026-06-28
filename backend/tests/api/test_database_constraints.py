import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import ClinicServicePrice


API_KEY = {"X-API-Key": "example-secret"}


def import_payload():
    return {
        "source": "clinic_partner_api",
        "clinic": {
            "external_id": "clinic_constraint",
            "name": "Constraint Clinic",
            "city": "Astana",
            "address": "Constraint street 10",
        },
        "branch": {
            "external_id": "branch_constraint",
            "name": "Main branch",
            "city": "Astana",
            "address": "Constraint street 10",
        },
        "services": [
            {
                "external_id": "srv_constraint",
                "name": "Constraint service",
                "category": "Diagnostics",
                "price": 25000,
                "currency": "KZT",
                "updated_at": "2026-06-17",
            }
        ],
    }


def test_current_price_unique_constraint_prevents_duplicates(client, db_session):
    response = client.post("/api/v1/import/prices", json=import_payload(), headers=API_KEY)
    assert response.status_code == 200

    price = db_session.scalar(select(ClinicServicePrice))
    duplicate = ClinicServicePrice(
        clinic_id=price.clinic_id,
        branch_id=price.branch_id,
        service_id=price.service_id,
        normalized_service_id=price.normalized_service_id,
        price=price.price,
        currency=price.currency,
        is_available=True,
        updated_at=price.updated_at,
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
