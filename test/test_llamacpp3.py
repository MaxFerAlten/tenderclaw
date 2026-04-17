import httpx
import json


async def test():
    # Method 1: base_url without /v1
    base = "http://localhost:3080"
    async with httpx.AsyncClient(base_url=base, timeout=3) as c:
        r = await c.get("/v1/models")
        print("Method 1 - Status:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("Method 1 - Data keys:", data.keys())
            print("Method 1 - Model IDs:", [m.get("id") for m in data.get("data", []) if m.get("id")])


import asyncio

asyncio.run(test())
