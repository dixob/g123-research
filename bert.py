from transformers import AutoTokenizer, AutoModel
import torch
import torch.nn.functional as F

model_name = 'distilbert-base-uncased'
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

def get_embedding(text):
    inputs = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        outputs = model(**inputs)
    # Mean pool over token embeddings
    return outputs.last_hidden_state.mean(dim=1)

# Test: similar meanings should have similar embeddings
emb1 = get_embedding('battle screen with low health')
emb2 = get_embedding('combat scene player is injured')
emb3 = get_embedding('main menu screen')

sim_12 = F.cosine_similarity(emb1, emb2).item()
sim_13 = F.cosine_similarity(emb1, emb3).item()

print(f'battle/combat similarity: {sim_12:.3f}')  # should be high
print(f'battle/menu similarity:   {sim_13:.3f}')  # should be lower
