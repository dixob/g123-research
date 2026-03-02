from transformers import AutoTokenizer, AutoModelForSequenceClassification
from peft import LoraConfig, get_peft_model, TaskType
from torch.utils.data import DataLoader, Dataset
import torch
import torch.nn as nn

# ── Training data: text descriptions of game screens ───────────
SCREEN_DATA = [
    ('Battle screen with HP bars and skill buttons', 0),
    ('Player vs enemy combat, low health warning', 0),
    ('Attack and defend options visible, SP gauge', 0),
    ('Main menu with play button and settings', 1),
    ('Title screen showing game logo and start game', 1),
    ('Navigation menu with multiple game modes', 1),
    ('Character inventory with equipment slots', 2),
    ('Item list with weapons and armor', 2),
    ('Storage screen with sortable items', 2),
]
LABELS = {0: 'battle', 1: 'menu', 2: 'inventory'}

# ── Dataset class ─────────────────────────────────────────────
class ScreenDataset(Dataset):
    def __init__(self, data, tokenizer):
        self.data = data
        self.tokenizer = tokenizer
    def __len__(self): return len(self.data)
    def __getitem__(self, i):
        text, label = self.data[i]
        enc = self.tokenizer(text, padding='max_length',
                             truncation=True, max_length=64, return_tensors='pt')
        return {k: v.squeeze(0) for k, v in enc.items()}, torch.tensor(label)

# ── Load model and add LoRA ─────────────────────────────────────
model_name = 'distilbert-base-uncased'
tokenizer = AutoTokenizer.from_pretrained(model_name)
base_model = AutoModelForSequenceClassification.from_pretrained(
    model_name, num_labels=3)

lora_config = LoraConfig(
    task_type=TaskType.SEQ_CLS,
    r=16,
    lora_alpha=32,
    target_modules=['q_lin', 'v_lin'],
    lora_dropout=0.1
)
model = get_peft_model(base_model, lora_config)
model.print_trainable_parameters()

# ── Training ─────────────────────────────────────────────────
dataset = ScreenDataset(SCREEN_DATA, tokenizer)
loader = DataLoader(dataset, batch_size=3, shuffle=True)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4)
loss_fn = nn.CrossEntropyLoss()

for epoch in range(20):
    total_loss = 0
    for batch, labels in loader:
        optimizer.zero_grad()
        outputs = model(**batch)
        loss = loss_fn(outputs.logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    if epoch % 5 == 0:
        print(f'Epoch {epoch}: loss = {total_loss:.4f}')

# ── Test the fine-tuned model ──────────────────────────────────
model.eval()
test_texts = [
    'Fighting enemy with skill gauge active',
    'Settings and game modes screen',
    'Equipment management with stats',
]

for text in test_texts:
    enc = tokenizer(text, return_tensors='pt', padding=True, truncation=True)
    with torch.no_grad():
        logits = model(**enc).logits
    pred = torch.argmax(logits).item()
    print(f'{text[:40]:42s} -> {LABELS[pred]}')
