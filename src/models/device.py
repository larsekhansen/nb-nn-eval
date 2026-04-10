"""
Auto-detect the best available device: CUDA > MPS > CPU.

MPS (Metal Performance Shaders) is Apple Silicon's GPU acceleration.
Available on M1/M2/M3/M4 Macs with PyTorch >= 1.12.
"""
from __future__ import annotations

import torch

_device = None


def get_device() -> torch.device:
    global _device
    if _device is not None:
        return _device

    if torch.cuda.is_available():
        _device = torch.device("cuda")
        print(f"[device] Using CUDA ({torch.cuda.get_device_name(0)})", flush=True)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        _device = torch.device("mps")
        print("[device] Using MPS (Apple Silicon GPU)", flush=True)
    else:
        _device = torch.device("cpu")
        print("[device] Using CPU", flush=True)

    return _device


def device_name() -> str:
    d = get_device()
    if d.type == "cuda":
        return f"CUDA ({torch.cuda.get_device_name(0)})"
    if d.type == "mps":
        return "MPS (Apple Silicon)"
    return "CPU"
