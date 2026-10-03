import httpx
import asyncio

API_URL = "https://shiv-database.onrender.com"
PROJECT_ID = "shivl"

async def setup():
    async with httpx.AsyncClient(base_url=API_URL) as client:
        print("1. Registering admin user...")
        reg_res = await client.post("/auth/register", json={
            "email": "admin@example.com",
            "username": "admin",
            "password": "supersecurepassword123",
            "metadata": {"name": "Admin"}
        })
        
        if reg_res.status_code == 200:
            print("Successfully registered admin@example.com!")
        elif reg_res.status_code == 400 and "exists" in reg_res.text:
            print("User already exists, proceeding to login...")
        else:
            print("Failed to register:", reg_res.text)

        print("\n2. Logging in to get Bearer Token...")
        login_res = await client.post("/auth/login", json={
            "email_or_username": "admin@example.com",
            "password": "supersecurepassword123"
        })
        
        if login_res.status_code != 200:
            print("Login failed!", login_res.text)
            return

        token_data = login_res.json()["data"]
        access_token = token_data["access_token"]
        print("Login successful! Acquired Bearer token.")

        print(f"\n3. Creating project API key for '{PROJECT_ID}'...")
        key_res = await client.post(
            f"/api-keys/{PROJECT_ID}?name={PROJECT_ID}_key",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if key_res.status_code == 200:
            print("\nSUCCESS! Here is your API key:")
            print("========================================")
            print(key_res.json()["data"]["raw_key"])
            print("========================================")
            print("Save this raw_key somewhere safe!")
        else:
            print("Failed to create API key:", key_res.text)

if __name__ == "__main__":
    asyncio.run(setup())
