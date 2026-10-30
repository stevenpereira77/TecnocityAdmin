"""Product-image validation and safe, space-bounded image encoding.

The encoded bytes are stored on the Product row, so database snapshots and
Google Drive database backups preserve the catalogue images automatically.
"""
from __future__ import annotations

from pathlib import Path

MAX_SOURCE_IMAGE_BYTES = 20 * 1024 * 1024
MAX_STORED_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_EDGE = 1400
SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

_SIGNATURES = {
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (),  # RIFF + size + WEBP; validated separately below.
    "bmp": (b"BM",),
    "gif": (b"GIF87a", b"GIF89a"),
}


def validate_image_file(path: str | Path) -> Path:
    """Check file existence, extension, size and recognizable image signature."""
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError("Selecciona un archivo de imagen existente.")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("Formato no admitido. Usa JPG, PNG, WEBP, BMP o GIF.")
    size = source.stat().st_size
    if size <= 0:
        raise ValueError("La imagen está vacía.")
    if size > MAX_SOURCE_IMAGE_BYTES:
        raise ValueError("La imagen supera el límite de 20 MB.")
    with source.open("rb") as fh:
        header = fh.read(16)
    kind = "jpeg" if suffix in {".jpg", ".jpeg"} else suffix[1:]
    if kind == "webp":
        valid = len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    else:
        valid = any(header.startswith(sig) for sig in _SIGNATURES.get(kind, ()))
    if not valid:
        raise ValueError("El archivo no coincide con un formato de imagen válido.")
    return source


def validate_product_image_data(data: bytes | bytearray | memoryview | None) -> bytes | None:
    """Validate the compressed image stored in SQLite (normally optimized JPEG)."""
    if data is None:
        return None
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise ValueError("Los datos de imagen no tienen un formato válido.")
    payload = bytes(data)
    if not payload:
        return None
    if len(payload) > MAX_STORED_IMAGE_BYTES:
        raise ValueError("La imagen optimizada supera el límite de 2 MB.")
    valid = (
        payload.startswith(_SIGNATURES["jpeg"][0])
        or payload.startswith(_SIGNATURES["png"][0])
        or payload.startswith(_SIGNATURES["bmp"][0])
        or any(payload.startswith(sig) for sig in _SIGNATURES["gif"])
        or (len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP")
    )
    if not valid:
        raise ValueError("Los datos suministrados no parecen ser una imagen reconocida.")
    return payload


def encode_product_image(path: str | Path) -> bytes:
    """Read and compress a selected photo to an orientation-correct JPEG.

    Uses Qt's image reader so images are decoded at a bounded display size.
    The white canvas avoids black backgrounds when PNGs with transparency are
    converted to JPEG. Imports are local to keep business-layer tests Qt-free.
    """
    source = validate_image_file(path)
    from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
    from PySide6.QtGui import QImage, QImageReader, QPainter

    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() <= 0 or size.height() <= 0:
        raise ValueError("No se pudieron leer las dimensiones de la imagen.")
    # Reject pathological dimensions instead of risking excessive memory use.
    if size.width() * size.height() > 250_000_000:
        raise ValueError("La imagen tiene dimensiones demasiado grandes.")
    reader.setScaledSize(size.scaled(QSize(MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        detail = reader.errorString().strip()
        raise ValueError(f"No se pudo abrir la imagen.{(' ' + detail) if detail else ''}")

    canvas = QImage(image.size(), QImage.Format.Format_RGB32)
    canvas.fill(Qt.GlobalColor.white)
    painter = QPainter(canvas)
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()

    for max_edge, quality in ((1400, 88), (1100, 82), (900, 76)):
        if max(canvas.width(), canvas.height()) > max_edge:
            canvas = canvas.scaled(
                QSize(max_edge, max_edge),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        buffer = QBuffer()
        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            raise ValueError("No se pudo preparar la imagen para guardarla.")
        try:
            if not canvas.save(buffer, "JPEG", quality):
                raise ValueError("No se pudo comprimir la imagen seleccionada.")
            payload = bytes(buffer.data())
        finally:
            buffer.close()
        if len(payload) <= MAX_STORED_IMAGE_BYTES:
            return validate_product_image_data(payload) or b""
    raise ValueError("No se pudo reducir la imagen a un tamaño seguro. Prueba con otra foto.")


def encode_product_thumbnail(image_data: bytes) -> bytes:
    """Create a compact JPEG thumbnail from an already validated full image."""
    from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
    from PySide6.QtGui import QImage, QPainter

    image = QImage.fromData(bytes(image_data))
    if image.isNull():
        raise ValueError("No se pudo generar la miniatura de la imagen.")
    size = image.size().scaled(QSize(240, 240), Qt.AspectRatioMode.KeepAspectRatio)
    image = image.scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    canvas = QImage(image.size(), QImage.Format.Format_RGB32)
    canvas.fill(Qt.GlobalColor.white)
    painter = QPainter(canvas)
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
        raise ValueError("No se pudo preparar la miniatura.")
    try:
        if not canvas.save(buffer, "JPEG", 72):
            raise ValueError("No se pudo comprimir la miniatura.")
        payload = bytes(buffer.data())
    finally:
        buffer.close()
    if len(payload) > 256 * 1024:
        raise ValueError("La miniatura generada supera el límite permitido.")
    return payload
