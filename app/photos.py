"""Compress uploaded photos (~100 KB) and store them in the database."""
import io
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlmodel import Session

from .models import Photo

MAX_UPLOAD = 12 * 1024 * 1024


async def save_photo(session: Session, upload: Optional[UploadFile]) -> Optional[int]:
    if upload is None or not upload.filename:
        return None
    raw = await upload.read()
    if not raw:
        return None
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "Photo too large (max 12 MB)")
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((1280, 1280))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70, optimize=True)
        data = buf.getvalue()
    except Exception:
        raise HTTPException(400, "Could not read that image")
    p = Photo(data=data, mime="image/jpeg")
    session.add(p)
    session.flush()
    return p.id
