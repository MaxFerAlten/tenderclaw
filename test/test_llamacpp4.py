import httpx
import json


async def test():
    # Test with /v1 suffix
    base = "http://localhost:3080/v1"
    async with httpx.AsyncClient(base_url=base, timeout=3) as c:
        r = await c.get("/v1/models")
        print("With /v1 suffix - Status:", r.status_code)

    # Test without /v1
    base = "http://localhost:3080"
    async with httpx.AsyncClient(base_url=base, timeout=3) as c:
        r = await c.get("/v1/models")
        print("Without /v1 - Status:", r.status_code)
        data = r.json()
        print("Model IDs:", [m.get("id") for m in data.get("data", []) if m.get("id")])


import asyncio

asyncio.run(test())
