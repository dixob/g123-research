from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import requests, torch
import torch.nn.functional as F # for cosine similarity

model = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
model_clip = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")

image = Image.open(r'C:\Projects\g123_research\images\ss1.png').convert('RGB')

labels = ['anime RPG combat screen with HP bars', 'main menu', 'inventory', 'shop', 'dialogue']

inputs = processor(text=labels, images = image, return_tensors = 'pt', padding=True )

with torch.no_grad(): # get CLIP's output for the image and text
    outputs = model_clip(**inputs) # get the image-text similarity scores (logits)
    logits = outputs.logits_per_image 
    probs = F.softmax(logits, dim=1) 

for label, prob in zip(labels, probs[0]): # print each label and its probability
    print(f'{label:20s}: {prob.item():.3f}') #