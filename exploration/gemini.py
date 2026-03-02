from google import genai
from PIL import Image
from dotenv import load_dotenv
import os, json, re

load_dotenv()
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def extract_game_state_gemini(image_path):
    img = Image.open(image_path)
    
    prompt = '''
Analyze this G123 anime game screenshot. Respond with ONLY a raw JSON object,
no markdown, no code fences, no explanation.

{
  "screen_type": "battle|menu|inventory|shop|loading|dialogue",
  "player_hp": null,
  "user_level": "...",
  "level_name": "...",
  "user_name": "..."
}'''

    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[img, prompt]
    )
    return response.text

result = extract_game_state_gemini('test_screenshot.png')
print(result)

cleaned = re.sub(r'```json\n?|\n?```', '', result).strip()
try:
    parsed = json.loads(cleaned)
    print('\nParsed successfully:', parsed)
except json.JSONDecodeError:
    print('Warning: Response was not valid JSON')