import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Azure CosmosDB Configuration
    COSMOSDB_ENDPOINT = os.getenv("COSMOS_DB_ENDPOINT")
    COSMOSDB_DATABASE_NAME = os.getenv("COSMOS_DB_DATABASE")
    COSMOSDB_CONTAINER_NAME = {
        "users": os.getenv("COSMOS_CONTAINERS_USERS"),
        "bookings": os.getenv("COSMOS_CONTAINERS_BOOKINGS"),
        "availabilities": os.getenv("COSMOS_CONTAINERS_AVAILABILITIES"),
        "notifications": os.getenv("COSMOS_CONTAINERS_NOTIFICATIONS"),
        "payments": os.getenv("COSMOS_CONTAINERS_PAYMENTS"),
        "gymcenters": os.getenv("COSMOS_CONTAINERS_GYMCENTERS")
    }
    
    # Azure Entra External ID Configuration
    AZURE_ENTRAID_TENANT_SUBDOMAIN = os.getenv("AZURE_ENTRAID_TENANT_SUBDOMAIN")
    AZURE_ENTRAID_TENANT_ID = os.getenv("AZURE_ENTRAID_TENANT_ID")
    AZURE_ENTRAID_CLIENT_ID = os.getenv("AZURE_ENTRAID_CLIENT_ID")
    AZURE_ENTRAID_SECRET = os.getenv("AZURE_ENTRAID_SECRET")
    AZURE_ENTRAID_B2C_EXTENSIONS = os.getenv("AZURE_ENTRAID_B2C_EXTENSIONS")
    
    # JWT Configuration
    JWT_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
    JWT_ALGORITHM = os.getenv("AUTH_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("AUTH_EXPIRATION", "30"))
    
    # Azure Email Communication Service
    EMAIL_CONNECTION_STRING = os.getenv("AZURE_COMSERV_CONNECTION_STRING")
    EMAIL_SENDER = os.getenv("AZURE_COMSERV_EMAIL")
    
    # Application Insights
    APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY")
    
    # Azure Storage
    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    
    # Stripe Configuration
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
