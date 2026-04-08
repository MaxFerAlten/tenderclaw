import asyncio
from openai import AsyncOpenAI
import os
import sys

# Import settings to get keys
sys.path.append(os.getcwd())
from backend.config import settings

async def test_openrouter():
    key = settings.openrouter_api_key
    if not key:
        print('OPENROUTER_API_KEY NOT SET IN CONFIG!')
        return
        
    print(f'Using OpenRouter API key: {key[:10]}...')
    client = AsyncOpenAI(api_key=key, base_url='https://openrouter.ai/api/v1')
    
    models = [
        'google/gemma-4-26b-a4b-it:free',
        'google/gemma-3-27b-it:free',
        'google/gemma-2-9b-it:free'
    ]
    
    for model in models:
        print(f'\n=================================')
        print(f'Testing model: {model} with prompt "ciao"')
        print(f'=================================')
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=[{'role': 'user', 'content': 'ciao'}],
                stream=True,
                max_tokens=50
            )
            print('Response chunks: ', end='')
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end='', flush=True)
            print('\n--- SUCCESS ---')
        except Exception as e:
            print(f'\n--- EXCEPTION CAUGHT ---')
            print(repr(e))
            print(f'Type: {type(e).__name__}')
            if hasattr(e, 'response'):
                print(f'HTTP Status: {e.response.status_code}')
                print(f'HTTP Body: {e.response.text}')

if __name__ == '__main__':
    asyncio.run(test_openrouter())
