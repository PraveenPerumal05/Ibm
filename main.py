from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
load_dotenv(BASE_DIR / ".env")


def load_json(filename: str) -> list[dict[str, Any]]:
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)


PRODUCTS = load_json("products.json")
ORDERS = load_json("orders.json")
MEMORY: dict[str, list[dict[str, str]]] = defaultdict(list)

app = FastAPI(title="ShopMate AI Customer Support", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_id: str = Field(default="demo", min_length=1, max_length=80)


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    suggestions: list[str] = []
    tool_used: str | None = None


def search_products(query: str) -> list[dict[str, Any]]:
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    ranked: list[tuple[int, dict[str, Any]]] = []
    for product in PRODUCTS:
        searchable = " ".join(
            [product["name"], product["category"], product["description"], *product["tags"]]
        ).lower()
        score = sum(term in searchable for term in terms)
        if score:
            ranked.append((score, product))
    return [product for _, product in sorted(ranked, key=lambda item: item[0], reverse=True)[:3]]


def get_order_status(order_id: str) -> dict[str, Any] | None:
    normalized = order_id.upper().replace("#", "")
    return next((order for order in ORDERS if order["id"] == normalized), None)


def recommend_products(message: str) -> list[dict[str, Any]]:
    category = next(
        (category for category in ("audio", "home", "fitness", "office") if category in message.lower()),
        None,
    )
    candidates = [product for product in PRODUCTS if not category or product["category"] == category]
    return sorted(candidates, key=lambda product: product["rating"], reverse=True)[:3]


def product_line(product: dict[str, Any]) -> str:
    return f"**{product['name']}** (${product['price']:.2f}) - {product['description']}"


def local_agent(message: str) -> tuple[str, str | None, list[str]]:
    lowered = message.lower()
    order_match = re.search(r"(?:order\s*)?#?([A-Z]{2}\d{4})", message, re.IGNORECASE)

    if order_match or "order" in lowered and any(word in lowered for word in ("status", "where", "track")):
        order = get_order_status(order_match.group(1) if order_match else "") if order_match else None
        if order:
            return (
                f"Order **{order['id']}** is **{order['status'].lower()}**. "
                f"Your {order['item']} is expected {order['eta']}.",
                "order_status",
                ["Find a product", "Recommend something for me"],
            )
        return (
            "I couldn't find that order. Please check the order ID, such as **NM1001**.",
            "order_status",
            ["Check order NM1001", "Find a product"],
        )

    if any(word in lowered for word in ("recommend", "suggest", "looking for", "gift")):
        products = recommend_products(message)
        return (
            "Here are a few picks I think you might like:\n\n" + "\n\n".join(product_line(product) for product in products),
            "recommendation",
            ["Show me audio products", "Where is order NM1001?"],
        )

    products = search_products(message)
    if products:
        return (
            "I found these matches:\n\n" + "\n\n".join(product_line(product) for product in products),
            "product_search",
            ["Recommend something similar", "Where is order NM1001?"],
        )

    return (
        "I can help you search products, check an order, or get recommendations. "
        "Try asking for wireless audio, a desk lamp, or order NM1001.",
        None,
        ["Find wireless headphones", "Check order NM1001", "Recommend a gift"],
    )


def gemini_agent(message: str, history: list[dict[str, str]]) -> tuple[str, str | None, list[str]] | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        context = json.dumps({"products": PRODUCTS, "orders": ORDERS}, indent=2)
        prompt = (
            "You are ShopMate, a concise e-commerce support agent. Use the catalog and orders below. "
            "Never invent availability or order details. If a tool-like lookup is needed, answer from the data. "
            "Keep replies under 100 words and use markdown.\n"
            f"Catalog/orders:\n{context}\nConversation:\n{history[-6:]}\nCustomer: {message}"
        )
        response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
        return response.text, "gemini", ["Find a product", "Check an order"]
    except Exception:
        return None


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    history = MEMORY[request.session_id]
    result = gemini_agent(request.message, history) or local_agent(request.message)
    reply, tool_used, suggestions = result
    history.extend([{"role": "user", "content": request.message}, {"role": "assistant", "content": reply}])
    del history[:-12]
    return ChatResponse(reply=reply, session_id=request.session_id, suggestions=suggestions, tool_used=tool_used)


@app.delete("/api/memory/{session_id}")
def clear_memory(session_id: str) -> dict[str, str]:
    MEMORY.pop(session_id, None)
    return {"status": "cleared"}
