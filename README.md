# ShopMate AI Customer Support

A small, runnable e-commerce support agent built with Python, FastAPI, and Gemini. It includes product search, order status, recommendations, lightweight conversation memory, a browser frontend, CORS, mock JSON data, and tests.

## Run in VS Code

1. Open this folder in VS Code.
2. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Optional: copy `.env.example` to `.env` and set `GEMINI_API_KEY`. The app works without it using a deterministic local agent.
5. Start the app:

   ```powershell
   uvicorn app.main:app --reload
   ```

6. Open http://127.0.0.1:8000 in a browser. API docs are at http://127.0.0.1:8000/docs.

## Test

```powershell
pytest -q
```

## Example requests

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/chat -Method Post -ContentType 'application/json' -Body '{"message":"Where is order NM1001?","session_id":"demo"}'
```

Mock records live in `data/products.json` and `data/orders.json`. The in-memory conversation history is capped to the most recent six messages per session and resets when the process restarts or the clear-memory endpoint is called.
