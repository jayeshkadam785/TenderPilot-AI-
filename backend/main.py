
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="TenderPilot AI API",
    description="Backend API for public tender discovery and analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
def home():
    return {
        "message": "TenderPilot AI Backend is running",
        "status": "success"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "TenderPilot AI"
    }


@app.post("/analyze")
def analyze_tender(tender: dict):
    return {
        "message": "Tender received for analysis",
        "tender": tender,
        "status": "received"
    }

