"""QR codes: read what's hidden inside without opening it. No AI needed for the decoding."""

import cv2
import numpy as np


def decode_qr_codes(image_bytes: bytes) -> list[str]:
    """Returns the text/links inside every QR code found in the image."""
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    detector = cv2.QRCodeDetector()
    results: list[str] = []

    for candidate in (img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)):
        try:
            ok, decoded, _, _ = detector.detectAndDecodeMulti(candidate)
        except cv2.error:
            ok, decoded = False, []
        if ok:
            results.extend(d for d in decoded if d)
        if not results:
            data, _, _ = detector.detectAndDecode(candidate)
            if data:
                results.append(data)
        if results:
            break
    return list(dict.fromkeys(results))
