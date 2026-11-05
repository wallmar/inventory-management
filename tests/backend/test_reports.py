"""
Tests for reports API endpoints.
"""
import re


class TestQuarterlyReportsEndpoints:
    """Test suite for quarterly report endpoints."""

    def test_get_quarterly_reports(self, client):
        """Test getting quarterly reports with the full structure."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for quarter in data:
            for field in ("quarter", "total_orders", "total_revenue", "avg_order_value", "fulfillment_rate"):
                assert field in quarter
            assert re.fullmatch(r"Q[1-4]-\d{4}", quarter["quarter"])

    def test_quarterly_totals_match_orders(self, client):
        """Test quarterly order counts and revenue add up to all orders."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()

        assert sum(q["total_orders"] for q in data) == len(orders)
        expected_revenue = sum(o["total_value"] for o in orders)
        assert abs(sum(q["total_revenue"] for q in data) - expected_revenue) < 0.01

    def test_quarterly_reports_by_warehouse(self, client):
        """Test the warehouse filter narrows the quarterly totals to that warehouse."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()
        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_quarterly_reports_by_month(self, client):
        """Test a quarter filter returns only that quarter."""
        data = client.get("/api/reports/quarterly?month=Q1-2025").json()
        assert [q["quarter"] for q in data] == ["Q1-2025"]


class TestMonthlyTrendsEndpoints:
    """Test suite for monthly trend endpoints."""

    def test_get_monthly_trends(self, client):
        """Test monthly trends are sorted by month with the full structure."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        months = [m["month"] for m in data]
        assert months == sorted(months)
        for month in data:
            assert re.fullmatch(r"\d{4}-\d{2}", month["month"])
            assert month["order_count"] > 0

    def test_monthly_trends_multiple_filters(self, client):
        """Test combined filters match the filtered orders endpoint."""
        query = "?warehouse=San Francisco&category=Sensors&status=Delivered"
        orders = client.get(f"/api/orders{query}").json()
        data = client.get(f"/api/reports/monthly-trends{query}").json()
        assert sum(m["order_count"] for m in data) == len(orders)

    def test_monthly_trends_by_month(self, client):
        """Test a month filter returns only that month."""
        data = client.get("/api/reports/monthly-trends?month=2025-03").json()
        assert [m["month"] for m in data] == ["2025-03"]
