from fastapi import FastAPI
import uvicorn
from src.routes.routes import router

app = FastAPI()

# Include routes
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
