import httpx
import json


async def test():
    async with httpx.AsyncClient(timeout=3) as c:
        r = await c.get("http://localhost:3080/v1/models")
        print("Status:", r.status_code)
        data = r.json()
        print("JSON keys:", data.keys())
        print("Data:", json.dumps(data, indent=2)[:500])


import asyncio

asyncio.run(test())
