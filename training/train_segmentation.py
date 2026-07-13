from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


CLASSES = ["background", "wall", "room", "door", "window"]


class DoubleConv(nn.Module):
    def __init__(self, input_channels: int, output_channels: int) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(input_channels, output_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels),
            nn.SiLU(inplace=True),
            nn.Conv2d(output_channels, output_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(output_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.block(value)


class FloorPlanUNet(nn.Module):
    def __init__(self, classes: int = len(CLASSES), base: int = 32) -> None:
        super().__init__()
        self.enc1 = DoubleConv(3, base)
        self.enc2 = DoubleConv(base, base * 2)
        self.enc3 = DoubleConv(base * 2, base * 4)
        self.enc4 = DoubleConv(base * 4, base * 8)
        self.bottleneck = DoubleConv(base * 8, base * 16)
        self.pool = nn.MaxPool2d(2)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, stride=2)
        self.dec4 = DoubleConv(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
        self.dec3 = DoubleConv(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
        self.dec2 = DoubleConv(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
        self.dec1 = DoubleConv(base * 2, base)
        self.output = nn.Conv2d(base, classes, 1)

    @staticmethod
    def _join(up: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        if up.shape[-2:] != skip.shape[-2:]:
            up = nn.functional.interpolate(up, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return torch.cat((skip, up), dim=1)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(value)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))
        center = self.bottleneck(self.pool(e4))
        d4 = self.dec4(self._join(self.up4(center), e4))
        d3 = self.dec3(self._join(self.up3(d4), e3))
        d2 = self.dec2(self._join(self.up2(d3), e2))
        d1 = self.dec1(self._join(self.up1(d2), e1))
        return self.output(d1)


@dataclass
class Record:
    image: Path
    mask: Path
    split: str
    source: str


class FloorPlanDataset(Dataset):
    def __init__(self, workspace: Path, records: list[Record], size: int, augment: bool) -> None:
        self.workspace = workspace
        self.records = records
        self.size = size
        self.augment = augment

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        record = self.records[index]
        image = Image.open(record.image).convert("RGB")
        mask = Image.open(record.mask).convert("L")
        if self.augment:
            if random.random() < 0.5:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                mask = mask.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if random.random() < 0.5:
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                mask = mask.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            rotations = random.choice((0, 0, 0, 90, 180, 270))
            if rotations:
                image = image.rotate(rotations, expand=True, fillcolor="white")
                mask = mask.rotate(rotations, expand=True, fillcolor=0)
            image = ImageEnhance.Contrast(image).enhance(random.uniform(0.82, 1.18))
            image = ImageEnhance.Brightness(image).enhance(random.uniform(0.86, 1.14))
        image, mask = letterbox_pair(image, mask, self.size)
        array = np.asarray(image, dtype=np.float32) / 255.0
        array = (array - np.asarray([0.485, 0.456, 0.406], dtype=np.float32)) / np.asarray([0.229, 0.224, 0.225], dtype=np.float32)
        tensor = torch.from_numpy(array.transpose(2, 0, 1)).float()
        target = torch.from_numpy(np.asarray(mask, dtype=np.int64).copy())
        return tensor, target


def letterbox_pair(image: Image.Image, mask: Image.Image, size: int) -> tuple[Image.Image, Image.Image]:
    scale = min(size / max(image.width, 1), size / max(image.height, 1))
    target = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    image = image.resize(target, Image.Resampling.BILINEAR)
    mask = mask.resize(target, Image.Resampling.NEAREST)
    output_image = Image.new("RGB", (size, size), "white")
    output_mask = Image.new("L", (size, size), 0)
    offset = ((size - target[0]) // 2, (size - target[1]) // 2)
    output_image.paste(image, offset)
    output_mask.paste(mask, offset)
    return output_image, output_mask


def read_records(workspace: Path) -> list[Record]:
    manifest = workspace / "processed" / "manifest.jsonl"
    if not manifest.exists():
        raise FileNotFoundError(f"Prepared manifest not found: {manifest}")
    deduplicated: dict[str, dict] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if line.strip():
            item = json.loads(line)
            deduplicated[str(item["id"])] = item
    records = [Record(
        image=workspace / item["image"],
        mask=workspace / item["mask"],
        split=item["split"],
        source=item.get("source", "unknown"),
    ) for item in deduplicated.values()]
    return [record for record in records if record.image.exists() and record.mask.exists()]


def class_weights(records: list[Record], sample_limit: int = 300) -> torch.Tensor:
    counts = np.ones(len(CLASSES), dtype=np.float64)
    for record in random.sample(records, min(len(records), sample_limit)):
        mask = np.asarray(Image.open(record.mask).convert("L"), dtype=np.int64)
        values, frequencies = np.unique(mask, return_counts=True)
        for value, frequency in zip(values, frequencies):
            if 0 <= value < len(CLASSES):
                counts[value] += frequency
    inverse = counts.sum() / counts
    weights = np.sqrt(inverse / inverse.mean())
    weights = np.clip(weights, 0.25, 6.0)
    return torch.tensor(weights, dtype=torch.float32)


def dice_loss(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    probabilities = logits.softmax(dim=1)
    one_hot = nn.functional.one_hot(target.clamp(0, len(CLASSES) - 1), len(CLASSES)).permute(0, 3, 1, 2).float()
    intersection = (probabilities * one_hot).sum(dim=(0, 2, 3))
    denominator = probabilities.sum(dim=(0, 2, 3)) + one_hot.sum(dim=(0, 2, 3))
    dice = (2 * intersection + 1.0) / (denominator + 1.0)
    return 1.0 - dice[1:].mean()


def confusion_matrix(logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    predicted = logits.argmax(dim=1).reshape(-1)
    expected = target.reshape(-1)
    valid = (expected >= 0) & (expected < len(CLASSES))
    indices = len(CLASSES) * expected[valid] + predicted[valid]
    return torch.bincount(indices, minlength=len(CLASSES) ** 2).reshape(len(CLASSES), len(CLASSES))


def metrics(matrix: torch.Tensor) -> dict:
    matrix = matrix.float()
    true_positive = matrix.diag()
    false_positive = matrix.sum(dim=0) - true_positive
    false_negative = matrix.sum(dim=1) - true_positive
    iou = true_positive / (true_positive + false_positive + false_negative).clamp_min(1)
    return {
        "mean_iou": round(float(iou[1:].mean()), 5),
        "iou": {name: round(float(iou[index]), 5) for index, name in enumerate(CLASSES)},
        "pixel_accuracy": round(float(true_positive.sum() / matrix.sum().clamp_min(1)), 5),
    }


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device, loss_function: nn.Module) -> tuple[float, dict]:
    model.eval()
    total_loss = 0.0
    matrix = torch.zeros((len(CLASSES), len(CLASSES)), dtype=torch.long)
    with torch.no_grad():
        for images, targets in loader:
            images, targets = images.to(device), targets.to(device)
            logits = model(images)
            loss = loss_function(logits, targets) + 0.35 * dice_loss(logits, targets)
            total_loss += float(loss)
            matrix += confusion_matrix(logits.cpu(), targets.cpu())
    return total_loss / max(len(loader), 1), metrics(matrix)


def export_onnx(model: nn.Module, destination: Path, size: int, device: torch.device) -> None:
    model.eval()
    example = torch.zeros(1, 3, size, size, device=device)
    torch.onnx.export(
        model,
        example,
        destination,
        input_names=["image"],
        output_names=["logits"],
        dynamic_axes={"image": {0: "batch", 2: "height", 3: "width"}, "logits": {0: "batch", 2: "height", 3: "width"}},
        opset_version=17,
    )
    metadata = {
        "architecture": "FloorPlanUNet",
        "labels": CLASSES,
        "input_size": size,
        "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        "threshold": 0.5,
        "output": "NCHW class logits",
    }
    destination.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export the local floor-plan segmentation model.")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("training-output"))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument("--image-size", type=int, default=512)
    parser.add_argument("--base-channels", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    workspace = args.workspace.expanduser().resolve()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = read_records(workspace)
    training_records = [record for record in records if record.split == "train"]
    validation_records = [record for record in records if record.split == "val"]
    if not training_records or not validation_records:
        raise RuntimeError("Both train and validation samples are required. Import more data or adjust the deterministic split.")

    use_cuda = torch.cuda.is_available() and args.device != "cpu"
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable.")
    device = torch.device("cuda" if use_cuda else "cpu")
    model = FloorPlanUNet(len(CLASSES), args.base_channels).to(device)
    weights = class_weights(training_records).to(device)
    cross_entropy = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.0001)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1), eta_min=args.learning_rate * 0.04)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")

    train_loader = DataLoader(FloorPlanDataset(workspace, training_records, args.image_size, True), batch_size=args.batch_size, shuffle=True, num_workers=args.workers, pin_memory=device.type == "cuda", drop_last=False)
    validation_loader = DataLoader(FloorPlanDataset(workspace, validation_records, args.image_size, False), batch_size=max(1, args.batch_size // 2), shuffle=False, num_workers=args.workers)
    best_iou = -1.0
    history: list[dict] = []
    best_path = output / "floorplan-segmentation-best.pt"

    for epoch in range(1, args.epochs + 1):
        model.train()
        running = 0.0
        for images, targets in train_loader:
            images, targets = images.to(device, non_blocking=True), targets.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                logits = model(images)
                loss = cross_entropy(logits, targets) + 0.35 * dice_loss(logits, targets)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            scaler.step(optimizer)
            scaler.update()
            running += float(loss)
        scheduler.step()
        validation_loss, validation_metrics = evaluate(model, validation_loader, device, cross_entropy)
        record = {
            "epoch": epoch,
            "train_loss": round(running / max(len(train_loader), 1), 6),
            "validation_loss": round(validation_loss, 6),
            "learning_rate": optimizer.param_groups[0]["lr"],
            **validation_metrics,
        }
        history.append(record)
        print(json.dumps(record))
        if validation_metrics["mean_iou"] > best_iou:
            best_iou = validation_metrics["mean_iou"]
            torch.save({"model": model.state_dict(), "classes": CLASSES, "image_size": args.image_size, "base_channels": args.base_channels, "metrics": validation_metrics}, best_path)

    checkpoint = torch.load(best_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model"])
    onnx_path = output / "floorplan-segmentation.onnx"
    export_onnx(model, onnx_path, args.image_size, device)
    (output / "training-history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    summary = {
        "device": str(device),
        "samples": {"train": len(training_records), "val": len(validation_records), "test": len([record for record in records if record.split == "test"])},
        "best_mean_iou": best_iou,
        "checkpoint": str(best_path),
        "onnx": str(onnx_path),
    }
    (output / "training-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
