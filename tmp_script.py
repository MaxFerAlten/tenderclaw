import re
import os

opencode = r'D:\MY_AI\claude-code\TenderClaw\backend\services\providers\opencode_provider.py'
openrouter = r'D:\MY_AI\claude-code\TenderClaw\backend\services\providers\openrouter_provider.py'

with open(opencode, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('OpenCodeProvider', 'OpenRouterProvider')
text = text.replace('tenderclaw.providers.opencode', 'tenderclaw.providers.openrouter')
text = text.replace('"opencode"', '"openrouter"')
text = text.replace('opencode_api_key', 'openrouter_api_key')
text = text.replace('OPENCODE_API_KEY', 'OPENROUTER_API_KEY')
text = text.replace('https://api.opencode.com/v1', 'https://openrouter.ai/api/v1')
text = text.replace('OpenCode provider', 'OpenRouter provider')
text = text.replace('OpenCode API error', 'OpenRouter API error')

text = re.sub(r'\"\"\"OpenCode provider.*?\"\"\"', '\"\"\"OpenRouter provider — unified access to 200+ models.\"\"\"', text, flags=re.DOTALL)
text = re.sub(r'\"\"\"Provider for OpenCode API.*?\"\"\"', '\"\"\"Provider for OpenRouter models (200+ models via openrouter.ai).\"\"\"', text, count=1)

with open(openrouter, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done porting to openrouter_provider.py")
