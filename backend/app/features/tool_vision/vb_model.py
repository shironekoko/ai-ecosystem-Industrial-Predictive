"""
Continuous Flank Wear (Vb) PyTorch Regressor Module
Architecture: Deep CNN Backbone with Residual / Skip Connections (ResNet18 / ResNet34)
Predicts continuous wear value Vb (in micrometers, µm) directly from optical flute images.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Union

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms


class ToolVbRegressor(nn.Module):
    """Continuous Flank Wear (Vb) Regressor using Deep CNN Backbone with Residual Connections"""
    def __init__(self, backbone_name: str = "resnet18", pretrained: bool = False, dropout: float = 0.25):
        super().__init__()
        self.backbone_name = backbone_name

        if backbone_name == "resnet18":
            weights = models.ResNet18_Weights.DEFAULT if pretrained else None
            base = models.resnet18(weights=weights)
            in_features = base.fc.in_features
            base.fc = nn.Identity()
            self.backbone = base
        elif backbone_name == "resnet34":
            weights = models.ResNet34_Weights.DEFAULT if pretrained else None
            base = models.resnet34(weights=weights)
            in_features = base.fc.in_features
            base.fc = nn.Identity()
            self.backbone = base
        elif backbone_name == "mobilenet_v3_large":
            weights = models.MobileNet_V3_Large_Weights.DEFAULT if pretrained else None
            base = models.mobilenet_v3_large(weights=weights)
            in_features = base.classifier[0].in_features
            base.classifier = nn.Identity()
            self.backbone = base
        else:
            raise ValueError(f"Unsupported backbone: {backbone_name}")

        self.head = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.SiLU(inplace=True),
            nn.Dropout(p=dropout),
            nn.Linear(256, 64),
            nn.BatchNorm1d(64),
            nn.SiLU(inplace=True),
            nn.Dropout(p=dropout * 0.5),
            nn.Linear(64, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.backbone(x)
        out = self.head(feat)
        return out.squeeze(-1)


# Standard preprocessing transforms
EVAL_TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


def classify_wear_band(vb_um: float) -> str:
    """Map continuous physical Vb (um) to industrial tool degradation state"""
    if vb_um < 100.0:
        return "sharp"
    elif vb_um < 140.0:
        return "used"
    else:
        return "dulled"


def compute_band_probabilities(vb_um: float) -> dict[str, float]:
    """Calculate pseudo-probabilities based on Gaussian distance to wear thresholds"""
    # Centers: sharp ~ 40um, used ~ 115um, dulled ~ 150+um
    mu_sharp, s_sharp = 40.0, 30.0
    mu_used, s_used = 115.0, 20.0
    mu_dulled, s_dulled = 160.0, 30.0

    p_s = float(np.exp(-0.5 * ((vb_um - mu_sharp) / s_sharp) ** 2))
    p_u = float(np.exp(-0.5 * ((vb_um - mu_used) / s_used) ** 2))
    p_d = float(np.exp(-0.5 * ((vb_um - mu_dulled) / s_dulled) ** 2))

    total = p_s + p_u + p_d + 1e-8
    return {
        "sharp": round(p_s / total, 4),
        "used": round(p_u / total, 4),
        "dulled": round(p_d / total, 4),
        "pred_vb_um": round(vb_um, 2)
    }
