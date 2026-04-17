from openai import AsyncOpenAI
import asyncio


async def test():
    client = AsyncOpenAI(api_key="llamacpp", base_url="http://localhost:3080/v1")
    # Use same system prompt as TenderClaw
    system = """You are TenderClaw, an advanced AI coding assistant.
You help users with software development tasks by reading, writing, and editing code,
running shell commands, searching codebases, and managing projects.

You have access to tools for file operations, shell commands, and code search.
Use them proactively to explore the codebase and verify your work."""

    resp = await client.chat.completions.create(
        model="Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "What files are in D:\\MY_AI\\claude-code\\TenderClaw\\backend ?"},
        ],
        max_tokens=500,
    )
    print(resp.choices[0].message.content)


asyncio.run(test())
