from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from backend.configuration.config import Config

# Initialize Azure credentials
credential = DefaultAzureCredential()

# Initialize the Cosmos Client
client = CosmosClient(
    url=Config.COSMOSDB_ENDPOINT,
    credential=credential
)

# Get database reference
database = client.get_database_client(Config.COSMOSDB_DATABASE_NAME)

# Dictionary to store container references
containers = {}
for container_key, container_name in Config.COSMOSDB_CONTAINER_NAME.items():
    containers[container_key] = database.get_container_client(container_name)

def get_container(container_key: str):
    """
    Dependency that provides the CosmosDB container client
    Args:
        container_key (str): Key of the container to get (users, bookings, etc.)
    Returns:
        Container client for the specified container
    """
    if container_key not in containers:
        raise ValueError(f"Container {container_key} not found")
    return containers[container_key]

def get_db(container_name: str):
    """Dependency injection function for FastAPI endpoints."""
    return get_container(container_name)
