"""Compatibility exports for the earlier local prototype module name."""

from __future__ import annotations

from .ocr import (
    make_paddle_ocr,
    normalize_paddle_result,
    ocr_batch,
    resolve_paddle_device,
    resolve_requested_device,
    run_single_image,
)

__all__ = [
    "make_paddle_ocr",
    "normalize_paddle_result",
    "ocr_batch",
    "resolve_paddle_device",
    "resolve_requested_device",
    "run_single_image",
]
