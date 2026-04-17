import httpx
import logging

logging.basicConfig(level=logging.INFO)


async def test():
    base_url = "http://localhost:3080/v1"
    base = base_url
    if base.endswith("/v1"):
        base = base[:-3]
    base = base.rstrip("/")
    print(f"Using base: {base}")

    async with httpx.AsyncClient(base_url=base, timeout=3) as c:
        r = await c.get("/v1/models")
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}")


import asyncio

asyncio.run(test())
