from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from src.routes.routes import router
from src.routes.ms_router import ms_router
from src.routes.trello_routers import trello_router

app = FastAPI()
# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://176.9.77.25","https://ai2osbackend.nexuslink.co.in","http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Include routes
app.include_router(router)
app.include_router(ms_router)
app.include_router(trello_router)

if __name__ == "__main__":
    import asyncio
    asyncio.run(uvicorn.run(app, host="127.0.0.1", port=8000))
