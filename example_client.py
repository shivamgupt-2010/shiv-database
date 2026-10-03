import asyncio
import httpx

API_URL = "http://localhost:8000"

async def main():
    async with httpx.AsyncClient(base_url=API_URL) as client:
        # 1. Check health
        print("Checking health...")
        res = await client.get("/health")
        print(res.json())

if __name__ == "__main__":
    asyncio.run(main())
