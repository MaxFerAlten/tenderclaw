import httpx
import json


async def test():
    base = "http://localhost:3080/v1"
    async with httpx.AsyncClient(base_url=base, timeout=3) as c:
        r = await c.get("/v1/models")
        print("Status:", r.status_code)
        data = r.json()
        print("JSON keys:", data.keys())
        if "data" in data and data["data"]:
            print("Model IDs:", [m.get("id") for m in data["data"] if m.get("id")])


import asyncio

asyncio.run(test())
