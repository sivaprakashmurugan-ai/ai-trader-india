# backend/app/api/main.py
from fastapi import FastAPI
from app.db.base import engine, Base
from . import routes_dashboard

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Intraday Trader API")

# Include dashboard routes
app.include_router(routes_dashboard.router, prefix="/dashboard", tags=["Dashboard"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}