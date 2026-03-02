import torch
import torch.nn as nn

# ── Tiny dataset: predict y = 2x ──────────────────────────────
x = torch.tensor([[1.0],[2.0],[3.0],[4.0],[5.0]])
y = torch.tensor([[2.0],[4.0],[6.0],[8.0],[10.0]])

# ── Model: single linear layer ────────────────────────────────
model = nn.Linear(1, 1)   # 1 input, 1 output

# ── Loss function and optimizer ───────────────────────────────
loss_fn = nn.MSELoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)

# ── Training loop ─────────────────────────────────────────────
for epoch in range(100):
    # TODO 1: Forward pass — get model's prediction for X
    prediction = model(x)

    # TODO 2: Compute loss — compare prediction to y
    loss = loss_fn(prediction, y)

    # TODO 3: Zero the gradients (always do this before backward)
    optimizer.zero_grad()

# TODO 4: Backward pass — compute gradients
    loss.backward()

    if epoch == 0:
        print(f'Gradient: {model.weight.grad.item():.4f}')
        print(f'Weight before: {model.weight.item():.4f}')
    optimizer.step()
    if epoch == 0:
        print(f'Weight after: {model.weight.item():.4f}')


    # TODO 5: Update weights
    optimizer.step()

    if epoch % 10 == 0:
        print(f'Epoch {epoch}: loss = {loss.item():.4f}')

print(f'Learned weight: {model.weight.item():.3f}')  # should be ~2.0
