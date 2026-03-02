from transformers import AutoModel
from peft import LoraConfig, get_peft_model
import torch

# Load DistilBERT
model = AutoModel.from_pretrained('distilbert-base-uncased')

# Count parameters before LoRA
total_params = sum(p.numel() for p in model.parameters())
print(f'Total parameters: {total_params:,}')

# Look at the Q weight matrix in layer 0
q_weight = model.transformer.layer[0].attention.q_lin.weight
print(f'Q weight shape: {q_weight.shape}')   # [768, 768]
print(f'Q weight parameters: {q_weight.numel():,}')

# Add LoRA
config = LoraConfig(
    r=16,                    # rank
    lora_alpha=32,           # scaling factor
    target_modules=['q_lin', 'v_lin'],  # which layers to adapt
    lora_dropout=0.1,
    bias='none'
)
lora_model = get_peft_model(model, config)

# Count trainable vs frozen
trainable = sum(p.numel() for p in lora_model.parameters() if p.requires_grad)
total = sum(p.numel() for p in lora_model.parameters()) 
print(f'Trainable (LoRA only): {trainable:,}')
print(f'Total: {total:,}')
print(f'Training {100 * trainable/total:.2f}% of parameters')

# See the new weight structure
lora_model.print_trainable_parameters() 

# Inspect a LoRA layer
lora_q = lora_model.base_model.model.transformer.layer[0].attention.q_lin 
print(f'\nLoRA A shape: {lora_q.lora_A["default"].weight.shape}')  # [16, 768]
print(f'LoRA B shape: {lora_q.lora_B["default"].weight.shape}')  # [768, 16]
print(f'A * B gives shape: [{lora_q.lora_B["default"].weight.shape[0]}, {lora_q.lora_A["default"].weight.shape[1]}]')
