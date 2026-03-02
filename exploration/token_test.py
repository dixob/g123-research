from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained('openai/clip-vit-base-patch32')

# Test game-relevant strings
texts = [
    'HP: 1523',
    'Limited time summon event',
    'ガチャイベント開催中',  # Japanese: Gacha event ongoing
    'Queen Blade battle screen',
]

for text in texts:
    tokens = tokenizer(text, return_tensors='pt')
    token_ids = tokens['input_ids'][0]
    decoded = [tokenizer.decode([t]) for t in token_ids]
    print(f'\nText: {text}')
    print(f'Tokens ({len(decoded)}): {decoded}')
