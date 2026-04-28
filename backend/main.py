from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from db.database import init_db
from routers import game, market, portfolio, simulation

app = FastAPI(title="Stock Trader Sim", version="1.0.0")

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API health (registered before static catch-all) ──────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

# ── API Routers ───────────────────────────────────────────────────
app.include_router(game.router)
app.include_router(market.router)
app.include_router(portfolio.router)
app.include_router(simulation.router)

# ── Frontend static files ─────────────────────────────────────────
# Resolve to stock-trader-sim/frontend/ regardless of cwd
FRONTEND_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

if os.path.exists(FRONTEND_DIR):
    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    # Serve every non-API path: try as a real file, fall back to index.html
    @app.get("/{full_path:path}")
    def serve_static(full_path: str):
        # Never intercept API calls (safety net — routers are registered first)
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
else:
    print(f"⚠️  Frontend directory not found at {FRONTEND_DIR}")


@app.on_event("startup")
def startup():
    init_db()
    print(f"🚀 Stock Trader Sim backend running")
    print(f"   Frontend: {FRONTEND_DIR}")