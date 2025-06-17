from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from src.routes.routes import router

app = FastAPI()
# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Include routes
app.include_router(router)

if __name__ == "__main__":
    import asyncio
    asyncio.run(uvicorn.run(app, host="127.0.0.1", port=8000))
