from transformers import CLIPProcessor, CLIPModel # for CLIP model and processor
from PIL import Image # for image processing
import requests # for downloading images from URLs
import torch # for tensor operations
import io

# Load the CLIP
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# Download a simple test image that works reliably
image = Image.open(r'C:\Projects\g123_research\images\ss1.png').convert('RGB')

# convert image to tensor
inputs = processor(images = image, return_tensors = 'pt')

# get vision embeddings
with torch.no_grad():
    vision_output = model.vision_model(**inputs)
    image_embeddings = vision_output.pooler_output

print(f'Embedding shape: {image_embeddings.shape}')
print(f'First 5 values: {image_embeddings[0][:5]}')
print('This is the image compressed to 512 numbers that capture visual meaning')
