import torch
from torch.utils.data import Dataset, DataLoader
from ai.data.aviris_loader import load_aviris_folder

class MethaneDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        rgb, mask = self.data[idx]

        rgb = torch.tensor(rgb, dtype=torch.float32).permute(2, 0, 1)
        mask = torch.tensor(mask, dtype=torch.float32).unsqueeze(0)

        return rgb, mask

class SimpleUNet(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = torch.nn.Conv2d(3, 16, 3, padding=1)
        self.conv2 = torch.nn.Conv2d(16, 32, 3, padding=1)
        self.conv3 = torch.nn.Conv2d(32, 1, 1)

    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        x = torch.sigmoid(self.conv3(x))
        return x


data = load_aviris_folder("ai/data/raw")  # ← put dataset here
dataset = MethaneDataset(data)
loader = DataLoader(dataset, batch_size=2, shuffle=True)

model = SimpleUNet()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
loss_fn = torch.nn.BCELoss()

for epoch in range(5):
    for x, y in loader:
        pred = model(x)
        loss = loss_fn(pred, y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    print("Epoch:", epoch, "Loss:", loss.item())

torch.save(model.state_dict(), "ai/models/methane_model.pth")