"""Upload validation and safe file handling."""
import hashlib
import re
import uuid
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = 16_000_000  # decompression-bomb guard

# extension -> {platform: magic bytes}
PACKAGE_MAGIC = {
    ".pkg": {"ps4": b"\x7fCNT", "ps5": b"\x7fCNT", "ps3": b"\x7fPKG"},
    ".zip": {p: b"PK\x03\x04" for p in ("ps3", "ps4", "ps5")},
    ".elf": {"ps4": b"\x7fELF", "ps5": b"\x7fELF"},
}
STORED_NAME = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{2,4}$")


class UploadError(ValueError):
    pass


def save_package(fs, platform, dest_dir: Path):
    """Validate extension + magic bytes, stream to disk, return (name, sha256, size)."""
    ext = Path(fs.filename or "").suffix.lower()
    magics = PACKAGE_MAGIC.get(ext)
    if not magics or platform not in magics:
        raise UploadError(f"A {ext or 'file without extension'} package is not allowed for {platform.upper()}.")
    head = fs.stream.read(8)
    fs.stream.seek(0)
    if not head.startswith(magics[platform]):
        raise UploadError("File content does not match its extension / platform.")
    name = uuid.uuid4().hex + ext
    path = dest_dir / name
    digest, size = hashlib.sha256(), 0
    with open(path, "wb") as out:
        while chunk := fs.stream.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)
            out.write(chunk)
    if size == 0:
        path.unlink(missing_ok=True)
        raise UploadError("Empty file.")
    return name, digest.hexdigest(), size


def save_icon(fs, dest_dir: Path):
    """Re-encode to a clean 512px-max PNG; strips metadata and any appended payload."""
    try:
        img = Image.open(fs.stream)
        if img.format not in ("PNG", "JPEG"):
            raise UploadError("Icon must be PNG or JPEG.")
        img.load()
        img = img.convert("RGBA")
        img.thumbnail((512, 512))
    except UploadError:
        raise
    except Exception:
        raise UploadError("Icon is not a valid image.")
    name = uuid.uuid4().hex + ".png"
    img.save(dest_dir / name, format="PNG")
    return name


def delete_stored(dest_dir: Path, name):
    """Delete only names we generated ourselves (blocks path traversal)."""
    if name and STORED_NAME.match(name):
        (dest_dir / name).unlink(missing_ok=True)
