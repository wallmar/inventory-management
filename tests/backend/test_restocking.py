"""
Tests for restocking API endpoints.
"""
from datetime import date, timedelta

import pytest

import mock_data


LEAD_TIMES = {
    "Circuit Boards": 14,
    "Sensors": 7,
    "Actuators": 21,
    "Controllers": 10,
    "Power Supplies": 5,
}
TREND_RANK = {"increasing": 3, "stable": 2, "decreasing": 1}


@pytest.fixture(autouse=True)
def reset_restocking_orders():
    """Submitted orders live in a module-level list; isolate each test from the others."""
    mock_data.restocking_orders.clear()
    yield
    mock_data.restocking_orders.clear()


def get_candidates(client, query=""):
    response = client.get(f"/api/restocking/candidates{query}")
    assert response.status_code == 200
    return response.json()


class TestRestockCandidatesEndpoints:
    """Test suite for restock recommendation endpoints."""

    def test_get_all_restock_candidates(self, client):
        """Test getting all restock candidates with the full structure."""
        data = get_candidates(client)
        assert isinstance(data, list)
        assert len(data) > 0

        for candidate in data:
            for field in (
                "item_sku", "item_name", "category", "trend", "current_demand",
                "forecasted_demand", "quantity_on_hand", "recommended_quantity",
                "unit_cost", "line_cost", "lead_time_days",
            ):
                assert field in candidate

    def test_restock_candidates_quantity_calculation(self, client):
        """Test recommended quantity is the forecast not covered by stock, and always positive."""
        for candidate in get_candidates(client):
            expected = candidate["forecasted_demand"] - candidate["quantity_on_hand"]
            assert candidate["recommended_quantity"] == expected
            assert candidate["recommended_quantity"] > 0
            assert abs(candidate["line_cost"] - expected * candidate["unit_cost"]) < 0.01

    def test_restock_candidates_exclude_sufficiently_stocked(self, client):
        """Test PSU-501 (420 on hand vs. 252 forecast) is not recommended."""
        skus = [c["item_sku"] for c in get_candidates(client)]
        assert "PSU-501" not in skus

    def test_restock_candidates_priority_order(self, client):
        """Test candidates are ordered by trend rank, increasing first."""
        ranks = [TREND_RANK[c["trend"]] for c in get_candidates(client)]
        assert ranks == sorted(ranks, reverse=True)
        assert ranks[0] == TREND_RANK["increasing"]

    def test_restock_candidates_lead_time_by_category(self, client):
        """Test lead time follows the per-category table."""
        for candidate in get_candidates(client):
            assert candidate["lead_time_days"] == LEAD_TIMES[candidate["category"]]

    def test_get_restock_candidates_by_category(self, client):
        """Test filtering candidates by category."""
        data = get_candidates(client, "?category=Sensors")
        assert [c["item_sku"] for c in data] == ["SNR-420"]

    def test_get_restock_candidates_category_all(self, client):
        """Test category=all returns the unfiltered list."""
        assert get_candidates(client, "?category=all") == get_candidates(client)


class TestRestockingOrdersEndpoints:
    """Test suite for submitting and listing restocking orders."""

    def test_create_restocking_order(self, client):
        """Test submitting an order prices lines on the server and sets delivery from lead time."""
        response = client.post("/api/restocking/orders", json={
            "budget": 10000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 450},
                {"item_sku": "CTL-330", "quantity": 96},
            ],
        })
        assert response.status_code == 201

        order = response.json()
        assert order["order_number"] == "RST-0001"
        assert order["status"] == "Submitted"
        assert order["budget"] == 10000
        assert abs(order["total_cost"] - (450 * 12.50 + 96 * 34.50)) < 0.01

        # Slowest line (Actuators, 21 days) determines delivery
        assert order["lead_time_days"] == 21
        created = date.fromisoformat(order["created_date"])
        assert created == date.today()
        assert date.fromisoformat(order["expected_delivery"]) == created + timedelta(days=21)

        assert len(order["items"]) == 2
        widget = order["items"][0]
        assert widget["item_name"] == "Industrial Widget Type A"
        assert widget["unit_cost"] == 12.50
        assert widget["lead_time_days"] == 21

    def test_create_restocking_order_ignores_client_price(self, client):
        """Test a unit_cost sent by the client does not change the server-computed total."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000,
            "items": [{"item_sku": "GSK-203", "quantity": 100, "unit_cost": 0.01}],
        })
        assert response.status_code == 201
        assert abs(response.json()["total_cost"] - 375.0) < 0.01

    def test_create_restocking_order_over_budget(self, client):
        """Test an order exceeding the budget is rejected and not stored."""
        response = client.post("/api/restocking/orders", json={
            "budget": 100,
            "items": [{"item_sku": "MTR-304", "quantity": 35}],
        })
        assert response.status_code == 400
        assert "exceeds budget" in response.json()["detail"]
        assert client.get("/api/restocking/orders").json() == []

    def test_create_restocking_order_duplicate_sku(self, client):
        """Test the same SKU twice in one order is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 10000,
            "items": [
                {"item_sku": "GSK-203", "quantity": 10},
                {"item_sku": "GSK-203", "quantity": 10},
            ],
        })
        assert response.status_code == 400
        assert "Duplicate SKU" in response.json()["detail"]

    def test_create_restocking_order_above_recommended_quantity(self, client):
        """Test ordering more than the recommended quantity is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1_000_000,
            "items": [{"item_sku": "GSK-203", "quantity": 601}],
        })
        assert response.status_code == 400
        assert "exceeds recommended" in response.json()["detail"]

    def test_create_restocking_order_sku_without_shortfall(self, client):
        """Test a forecast SKU that is sufficiently stocked (PSU-501) cannot be ordered."""
        response = client.post("/api/restocking/orders", json={
            "budget": 10000,
            "items": [{"item_sku": "PSU-501", "quantity": 1}],
        })
        assert response.status_code == 400

    def test_create_restocking_order_unknown_sku(self, client):
        """Test an unknown SKU is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000,
            "items": [{"item_sku": "NOPE-999", "quantity": 1}],
        })
        assert response.status_code == 400
        assert "Unknown SKU" in response.json()["detail"]

    def test_create_restocking_order_non_positive_quantity(self, client):
        """Test a zero quantity is rejected."""
        response = client.post("/api/restocking/orders", json={
            "budget": 1000,
            "items": [{"item_sku": "WDG-001", "quantity": 0}],
        })
        assert response.status_code == 400

    def test_create_restocking_order_empty_items(self, client):
        """Test an order without items fails validation."""
        response = client.post("/api/restocking/orders", json={"budget": 1000, "items": []})
        assert response.status_code == 422

    def test_get_restocking_orders_newest_first(self, client):
        """Test listing returns submitted orders, newest first, with sequential numbers."""
        assert client.get("/api/restocking/orders").json() == []

        for sku in ("GSK-203", "FLT-405"):
            response = client.post("/api/restocking/orders", json={
                "budget": 10000,
                "items": [{"item_sku": sku, "quantity": 10}],
            })
            assert response.status_code == 201

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        data = response.json()
        assert [o["order_number"] for o in data] == ["RST-0002", "RST-0001"]
        assert data[0]["items"][0]["item_sku"] == "FLT-405"


class TestDemandForecastPricing:
    """Test suite for the pricing fields on demand forecasts."""

    def test_demand_forecasts_have_category_and_cost(self, client):
        """Test every forecast carries a known category and a positive unit cost."""
        response = client.get("/api/demand")
        assert response.status_code == 200
        for forecast in response.json():
            assert forecast["category"] in LEAD_TIMES
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
