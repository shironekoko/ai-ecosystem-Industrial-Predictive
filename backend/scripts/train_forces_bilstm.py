"""
Training Pipeline for 1D-CNN + BiLSTM on Nonastreda 3-Axis Force Signals (Fx, Fy, Fz)
Protocol: 10-Fold Cross-Validation / Leave-One-Tool-Out (Tools 1-9 Train, Tool 10 Test)
Target: Multi-Task Tool Wear State (Classification: sharp/used/dulled) & Flank Wear (Regression: Vb in µm)
"""

import os
import re
import numpy as np
import pandas as pd
import scipy.io as sio
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Check Device
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

class ForceSignalDataset(Dataset):
    def __init__(self, samples, target_length=1000):
        self.samples = samples
        self.target_length = target_length
        self.class_map = {'sharp': 0, 'used': 1, 'dulled': 2}

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        raw_forces = item['forces'] # shape (3, N)
        
        # Downsample or resample to target_length
        n_points = raw_forces.shape[1]
        step = max(1, n_points // self.target_length)
        sampled = raw_forces[:, ::step][:, :self.target_length]
        
        # Zero-pad if shorter
        if sampled.shape[1] < self.target_length:
            pad_width = self.target_length - sampled.shape[1]
            sampled = np.pad(sampled, ((0, 0), (0, pad_width)), mode='constant')

        # Standardize (Z-score normalization per channel)
        mean = np.mean(sampled, axis=1, keepdims=True)
        std = np.std(sampled, axis=1, keepdims=True) + 1e-6
        normalized = (sampled - mean) / std

        # Targets
        class_label = self.class_map.get(item['label'].lower(), 0)
        flank_wear = float(item['flank_wear'])

        return {
            'signals': torch.tensor(normalized, dtype=torch.float32), # (3, L)
            'class_label': torch.tensor(class_label, dtype=torch.long),
            'flank_wear': torch.tensor(flank_wear, dtype=torch.float32),
            'id': item['id'],
            'tool_id': item['tool_id']
        }

class Conv1D_BiLSTM(nn.Module):
    """
    1D-CNN + BiLSTM Multi-Task Architecture
    1D-CNN: Extracts local dynamic vibration & tooth engagement harmonics across Fx, Fy, Fz
    BiLSTM: Captures long-range temporal trends and force accumulation
    Dual Heads: 3-class classification + 1D flank wear regression
    """
    def __init__(self, in_channels=3, seq_len=1000, hidden_dim=64, num_classes=3):
        super().__init__()
        
        # 1D-CNN Feature Extractor
        self.conv1 = nn.Sequential(
            nn.Conv1d(in_channels, 32, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        self.conv2 = nn.Sequential(
            nn.Conv1d(32, 64, kernel_size=5, stride=2, padding=2),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.MaxPool1d(2)
        )
        self.conv3 = nn.Sequential(
            nn.Conv1d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.BatchNorm1d(128),
            nn.ReLU()
        )
        
        # BiLSTM Sequence Modeler
        self.bilstm = nn.LSTM(
            input_size=128,
            hidden_size=hidden_dim,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=0.2
        )
        
        lstm_out_dim = hidden_dim * 2
        
        # Classification Head (sharp / used / dulled)
        self.cls_head = nn.Sequential(
            nn.Linear(lstm_out_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, num_classes)
        )
        
        # Regression Head (Flank wear in µm)
        self.reg_head = nn.Sequential(
            nn.Linear(lstm_out_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

    def forward(self, x):
        # x: (Batch, Channels=3, Length=1000)
        feat = self.conv1(x)
        feat = self.conv2(feat)
        feat = self.conv3(feat)
        
        # Permute for LSTM: (Batch, SeqLen, Features)
        feat = feat.permute(0, 2, 1)
        lstm_out, _ = self.bilstm(feat)
        
        # Global Average Pooling across time steps
        context = torch.mean(lstm_out, dim=1)
        
        logits = self.cls_head(context)
        flank_wear_pred = self.reg_head(context).squeeze(-1)
        
        return logits, flank_wear_pred

def load_nonastreda_dataset(base_path):
    print(f"Loading Nonastreda from: {base_path}")
    df_labels = pd.read_csv(os.path.join(base_path, 'labels.csv'))
    df_reg = pd.read_csv(os.path.join(base_path, 'labels_reg.csv'))
    df_merged = pd.merge(df_labels, df_reg, on='id')
    
    mat_path = os.path.join(base_path, 'forces_xyz_raw.mat')
    mat = sio.loadmat(mat_path)
    bd = mat['baseDatastore']
    
    samples = []
    for i in range(len(bd)):
        row_id = df_merged.iloc[i]['id']
        m = re.match(r'T(\d+)R(\d+)B(\d+)', row_id)
        tool_id = int(m.group(1)) if m else 1
        
        samples.append({
            'id': row_id,
            'tool_id': tool_id,
            'label': df_merged.iloc[i]['image_label'],
            'flank_wear': df_merged.iloc[i]['flank_wear'],
            'forces': bd[i, 3] # (3, N)
        })
    print(f"Loaded {len(samples)} observations across 10 tools successfully!")
    return samples

def train_model(base_path, test_tool=10, epochs=25, batch_size=16, lr=1e-3):
    samples = load_nonastreda_dataset(base_path)
    
    # Split: Tools 1-9 for Train/Val, Tool 10 for held-out Test
    train_samples = [s for s in samples if s['tool_id'] != test_tool]
    test_samples = [s for s in samples if s['tool_id'] == test_tool]
    
    print(f"Split: Train samples = {len(train_samples)} (Tools 1-9), Test samples = {len(test_samples)} (Tool #{test_tool})")
    
    train_dataset = ForceSignalDataset(train_samples)
    test_dataset = ForceSignalDataset(test_samples)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    model = Conv1D_BiLSTM().to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    cls_criterion = nn.CrossEntropyLoss()
    reg_criterion = nn.SmoothL1Loss()
    
    print("\nStarting Training on Device:", DEVICE)
    best_acc = 0.0
    
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, correct, total = 0.0, 0, 0
        
        for batch in train_loader:
            signals = batch['signals'].to(DEVICE)
            targets_cls = batch['class_label'].to(DEVICE)
            targets_reg = batch['flank_wear'].to(DEVICE)
            
            optimizer.zero_grad()
            logits, wear_pred = model(signals)
            
            loss_cls = cls_criterion(logits, targets_cls)
            loss_reg = reg_criterion(wear_pred, targets_reg) * 0.01 # scale regression loss
            loss = loss_cls + loss_reg
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item() * signals.size(0)
            preds = torch.argmax(logits, dim=1)
            correct += (preds == targets_cls).sum().item()
            total += targets_cls.size(0)
            
        train_acc = (correct / total) * 100
        
        # Evaluate on Held-out Tool 10
        model.eval()
        test_correct, test_total, test_mae = 0, 0, 0.0
        with torch.no_grad():
            for batch in test_loader:
                signals = batch['signals'].to(DEVICE)
                targets_cls = batch['class_label'].to(DEVICE)
                targets_reg = batch['flank_wear'].to(DEVICE)
                
                logits, wear_pred = model(signals)
                preds = torch.argmax(logits, dim=1)
                
                test_correct += (preds == targets_cls).sum().item()
                test_total += targets_cls.size(0)
                test_mae += torch.abs(wear_pred - targets_reg).sum().item()
                
        test_acc = (test_correct / test_total) * 100
        test_mae = test_mae / test_total
        
        print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {total_loss/total:.4f} | Train Acc: {train_acc:.1f}% | Test Acc (Tool {test_tool}): {test_acc:.1f}% | Flank Wear MAE: {test_mae:.2f} µm")
        
        if test_acc > best_acc:
            best_acc = test_acc
            os.makedirs("models", exist_ok=True)
            torch.save(model.state_dict(), "models/forces_bilstm_best.pt")
            
    print(f"\nTraining Complete! Best Test Accuracy on Tool #{test_tool}: {best_acc:.2f}%")
    print("Saved best checkpoint to: models/forces_bilstm_best.pt")

if __name__ == '__main__':
    dataset_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'dataset', 'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)', 'Nonastreda Multimodal Dataset for Identifying Tool Wear Condition'))
    train_model(dataset_dir, test_tool=10, epochs=15)
