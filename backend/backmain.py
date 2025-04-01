from fastapi import FastAPI
from backend.routers import rou_booking, rou_availability, rou_message, rou_auth

app = FastAPI(
    title="GymAgent API",
    description="API for GymAgent application",
    version="1.0.0"
)

# Include all routers
app.include_router(rou_auth.router)  # Auth routes should typically be first
app.include_router(rou_booking.router)
app.include_router(rou_availability.router)
app.include_router(rou_message.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
