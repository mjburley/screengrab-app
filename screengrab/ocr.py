"""Extract text from an image using the OCR engine built into Windows 10/11
(``Windows.Media.Ocr``), via the pywinrt ``winrt-*`` packages.

Runs offline and needs no extra install beyond the pip packages — Windows
ships OCR models for the user's display languages.
"""
from __future__ import annotations

import asyncio
from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

# Windows OCR misreads small screen text at 1:1 (e.g. "tiny" -> "tim,'" at 9pt).
# Upscaling 2x fixed that in testing; 3x/4x gave no further improvement.
UPSCALE = 2

# Windows OCR returns *nothing* for text cropped tightly to its edges (a snug
# drag-selection, or a snug original capture). Padding with the image's own
# background colour fixes it: 8px was enough in testing (incl. dark mode);
# 16px leaves headroom.
PADDING = 16


class OcrError(RuntimeError):
    """Raised with a user-readable message when text extraction can't run."""


def extract_text(image: QImage) -> str:
    """Return the text found in ``image``, one line of text per line."""
    try:
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter
    except ImportError as exc:
        raise OcrError("Windows OCR support is missing from this build.") from exc

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise OcrError(
            "No Windows OCR language is installed.\n\n"
            "Add one under Settings → Time & language → Language & region."
        )

    # Work in raw pixels. A DPR-tagged capture (scaled display) would otherwise
    # be painted at its smaller logical size by _pad, losing detail.
    image = QImage(image)
    image.setDevicePixelRatio(1.0)
    image = _pad(image, PADDING)

    # Upscale for accuracy, but never past the engine's size limit (a wide
    # multi-monitor capture may even need scaling *down* to fit).
    longest = max(image.width(), image.height())
    scale = min(float(UPSCALE), OcrEngine.max_image_dimension / longest)
    if scale != 1.0:
        image = image.scaled(
            max(1, round(image.width() * scale)),
            max(1, round(image.height() * scale)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # ARGB32 is BGRA byte order in memory on little-endian Windows = BGRA8.
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    writer = DataWriter()
    writer.write_bytes(bytes(image.constBits()))
    bitmap = SoftwareBitmap.create_copy_from_buffer(
        writer.detach_buffer(), BitmapPixelFormat.BGRA8, image.width(), image.height()
    )

    try:
        result = asyncio.run(_recognise(engine, bitmap))
    except OSError as exc:  # WinRT failures surface as OSError(HRESULT)
        raise OcrError(f"Text extraction failed:\n{exc}") from exc
    return "\n".join(line.text for line in result.lines)


async def _recognise(engine, bitmap):
    return await engine.recognize_async(bitmap)


def _pad(image: QImage, margin: int) -> QImage:
    """Return ``image`` with a ``margin`` border in its most common edge colour."""
    w, h = image.width(), image.height()
    edge = [image.pixel(x, y) for x in range(w) for y in (0, h - 1)]
    edge += [image.pixel(x, y) for y in range(h) for x in (0, w - 1)]
    background = QColor.fromRgb(Counter(edge).most_common(1)[0][0])

    out = QImage(w + 2 * margin, h + 2 * margin, QImage.Format.Format_RGB32)
    out.fill(background)
    painter = QPainter(out)
    painter.drawImage(margin, margin, image)
    painter.end()
    return out
