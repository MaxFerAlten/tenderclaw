import asyncio
import sys

sys.path.insert(0, "backend")


async def test():
    from backend.config import settings
    import httpx

    raw_url = settings.llamacpp_base_url
    print(f"Raw URL from settings: {raw_url}")

    base = raw_url.rstrip("/")
    print(f"After rstrip: {base}")

    if base.endswith("/v1"):
        base = base[:-3]
        print(f"After removing /v1: {base}")

    async with httpx.AsyncClient(base_url=base, timeout=3.0) as client:
        resp = await client.get("/v1/models")
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text[:200]}")


asyncio.run(test())
