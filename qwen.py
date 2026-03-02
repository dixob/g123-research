from openai import OpenAI
from dotenv import load_dotenv
import os, json, re, base64

load_dotenv()

client = OpenAI(
    api_key=os.getenv('TOGETHER_API_KEY'),
    base_url='https://api.together.xyz/v1'
)

def encode_image(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')

def extract_game_state(image_path, model):
    image_data = encode_image(image_path)
    
    prompt = '''Analyze this game screenshot and respond with ONLY a raw JSON object, no markdown, no code fences, no explanation.

{
  "screen_type": "battle or menu or inventory or shop or loading or dialogue",
  "player_hp": null,
  "user_level": "...",
  "level_name": "...",
  "user_name": "..."
}'''

    response = client.chat.completions.create(
        model=model,
        max_tokens=1000,
        temperature=0.1,
        messages=[{
            'role': 'user',
            'content': [
                {'type': 'image_url',
                 'image_url': {'url': f'data:image/png;base64,{image_data}'}},
                {'type': 'text', 'text': prompt}
            ]
        }]
    )
    
    content = response.choices[0].message.content
    print(f'Finish reason: {response.choices[0].finish_reason}')
    print(f'Raw: {repr(content)}')
    return content

models = {
    'Qwen3-VL-32B': 'Qwen/Qwen3-VL-32B-Instruct',
}

for name, model_id in models.items():
    print(f'\n{"="*50}')
    print(f'Model: {name}')
    print('='*50)
    
    try:
        result = extract_game_state('test_screenshot.png', model_id)
        if result:
            cleaned = re.sub(r'```json\n?|\n?```', '', result).strip()
            try:
                parsed = json.loads(cleaned)
                print('Parsed successfully:')
                print(json.dumps(parsed, indent=2))
            except json.JSONDecodeError:
                print('Warning: not valid JSON')
                print(f'Content: {result}')
        else:
            print('Empty response')
    except Exception as e:
        print(f'Error: {e}')