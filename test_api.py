import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("N8N_API_KEY", "")

response = httpx.get(
    "http://localhost:5678/api/v1/workflows",
    headers={"X-N8N-API-KEY": api_key},
    timeout=10.0,
)

print(f"Status: {response.status_code}")
print(response.json())
