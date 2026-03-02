import openai, base64, json
from pathlib import Path
from dotenv import load_dotenv # for loading API keys from .env file
import os

load_dotenv() # Load API keys from .env file
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def encode_image(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def extract_game_state(image_path):
    image_data = encode_image(image_path)
    response = client.chat.completions.create(
        model='gpt-4o',
        max_tokens=500,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image_url',
                 'image_url': {'url': f'data:image/png;base64,{image_data}'}},
                {'type': 'text', 'text': '''
Analyze this G123 anime game screenshot. Respond with ONLY a raw JSON object, 
no markdown, no code fences, no explanation.

Rules:
- player_hp: extract the NUMBER only from HP bars (e.g. if you see "50/100" return 50)
- screen_type: choose exactly one from: battle, menu, inventory, shop, loading, dialogue
- visible_ui_elements: buttons and interactive elements only, not text labels

{
  "screen_type": "...",
  "player_hp": null,
                 "user_level": "...",
                 "level_name": "...",
                 "user_name": "..."
  ...
}'''}
            ]
        }]
    )
    return response.choices[0].message.content

# Test with a screenshot — save any G123 screenshot as 'test_screenshot.png'
result = extract_game_state('test_screenshot.png')
print(result)
try:
    parsed = json.loads(result)
    print('\nParsed successfully:', parsed)
except json.JSONDecodeError:
    print('Warning: Response was not valid JSON')
