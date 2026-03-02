import torch
import torch.nn as nn

# HP values (normalized 0-1): below 0.3 = danger
X = torch.tensor([[0.9],[0.7],[0.5],[0.3],[0.2],[0.1],[0.05],[0.8],[0.6],[0.25]])
y = torch.tensor([[0],[0],[0],[0],[1],[1],[1],[0],[0],[1]], dtype=torch.float)

# ── Model: two layers ─────────────────────────────────────────
class HPClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.layer1 = nn.Linear(1, 8)     # 1 input -> 8 hidden
        self.relu   = nn.ReLU()
        self.layer2 = nn.Linear(8, 1)     # 8 hidden -> 1 output
        self.sigmoid = nn.Sigmoid()        # output between 0 and 1

    def forward(self, x):
        x = self.relu(self.layer1(x))
        x = self.sigmoid(self.layer2(x))
        return x

model = HPClassifier()
loss_fn = nn.BCELoss()   # Binary cross-entropy for 0/1 classification
optimizer = torch.optim.Adam(model.parameters(), lr=0.05)

# TODO: Write the 100-epoch training loop
# (same structure as Exercise 1.1 — forward, loss, zero_grad, backward, step)

for epoch in range(100):
    #forward pass
    prediction = model(X)
    #compute loss
    loss = loss_fn(prediction, y)
    #zero the gradients
    optimizer.zero_grad()
    #backward pass
    loss.backward()
    #update weights
    optimizer.step()

# Test the trained model
with torch.no_grad():
    test_hp = torch.tensor([[0.15]])   # 15% HP — should be danger (1)
    print(f'HP 15%: {model(test_hp).item():.2f}')  # should be close to 1
    test_hp2 = torch.tensor([[0.85]])  # 85% HP — should be safe (0)
    print(f'HP 85%: {model(test_hp2).item():.2f}') # should be close to 0
