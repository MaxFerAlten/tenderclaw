import asyncio
import sys

sys.path.insert(0, "backend")


async def test():
    import httpx

    # Simulate what the endpoint does
    base_url = "http://localhost:3080"
    async with httpx.AsyncClient(base_url=base_url, timeout=3.0) as client:
        resp = await client.get("/v1/models")
        print(f"Status: {resp.status_code}")
        if resp.status_code in (200, 404):
            data = resp.json()
            print(f"JSON keys: {data.keys()}")
            model_list = data.get("data", [])
            print(f"data list: {model_list}")
            if model_list:
                models = [m.get("id", "") for m in model_list if m.get("id")]
                print(f"Models: {models}")


asyncio.run(test())
