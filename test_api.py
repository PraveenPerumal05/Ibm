from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_and_frontend():
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200


def test_product_search_tool():
    response = client.post("/api/chat", json={"message": "Find wireless headphones", "session_id": "products"})
    body = response.json()
    assert body["tool_used"] == "product_search"
    assert "CloudBeat" in body["reply"]


def test_order_status_tool():
    response = client.post("/api/chat", json={"message": "Where is order NM1001?", "session_id": "orders"})
    body = response.json()
    assert body["tool_used"] == "order_status"
    assert "out for delivery" in body["reply"].lower()


def test_recommendation_tool_and_memory_reset():
    session = "recommendations"
    response = client.post("/api/chat", json={"message": "Recommend an audio gift", "session_id": session})
    assert response.json()["tool_used"] == "recommendation"
    assert client.delete(f"/api/memory/{session}").json() == {"status": "cleared"}
