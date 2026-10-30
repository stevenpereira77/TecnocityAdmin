"""Reusable, theme-friendly product image preview widgets and helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout
from sqlalchemy import inspect as sqlalchemy_inspect

from app.config import AppSettings
from app.utils.paths import project_root


def _value(product: Any, key: str, default=None):
    if isinstance(product, dict):
        return product.get(key, default)
    # Product.image_data is deferred to keep 100-row catalogue pages lightweight.
    try:
        state = sqlalchemy_inspect(product)
        if key in state.unloaded:
            return default
    except (TypeError, AttributeError):
        pass
    return getattr(product, key, default)


def _legacy_image_candidates(raw_path: str) -> list[Path]:
    if not raw_path:
        return []
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return [path]
    candidates = [Path.cwd() / path, project_root() / path]
    # Earlier builds may have stored the relative path under the data folder.
    candidates.append(AppSettings.load().data_dir / path)
    unique: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


def load_product_pixmap(image_data: bytes | None, image_path: str = "", size: QSize = QSize(120, 100)) -> QPixmap:
    """Load an optimized database image or a legacy external image, preserving aspect ratio."""
    pixmap = QPixmap()
    if image_data:
        try:
            pixmap.loadFromData(bytes(image_data))
        except (TypeError, ValueError):
            pass
    if pixmap.isNull() and image_path:
        for candidate in _legacy_image_candidates(str(image_path)):
            if not candidate.is_file():
                continue
            reader = QImageReader(str(candidate))
            reader.setAutoTransform(True)
            original_size = reader.size()
            if original_size.isValid():
                reader.setScaledSize(original_size.scaled(size, Qt.AspectRatioMode.KeepAspectRatio))
            image = reader.read()
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                break
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


def product_pixmap(product: Any, size: QSize = QSize(120, 100)) -> QPixmap:
    # Catalogue/inventory pages prefer the small thumbnail and only fall back
    # to a full payload if it is already loaded (never trigger lazy DB I/O).
    thumbnail = _value(product, "image_thumbnail_data")
    full = _value(product, "image_data")
    return load_product_pixmap(
        thumbnail or full,
        str(_value(product, "image_path", "") or ""),
        size,
    )


class ProductImageDialog(QDialog):
    """Large preview dialog; it does not alter the original image dimensions."""

    def __init__(self, name: str, image_data: bytes | None = None, image_path: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Imagen del producto — {name}")
        self.setMinimumSize(420, 340)
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(name)
        title.setObjectName("sectionLabel")
        title.setWordWrap(True)
        layout.addWidget(title)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setObjectName("productImageLargePreview")
        self.image_label.setMinimumSize(360, 260)
        self.image_label.setText("Este producto todavía no tiene una imagen.")
        pixmap = load_product_pixmap(image_data, image_path, QSize(700, 520))
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap)
            self.image_label.setText("")
        layout.addWidget(self.image_label, 1)
