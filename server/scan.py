"""Optional ClamAV (clamd INSTREAM) scan. If CLAMD_ADDR is set, any failure rejects the upload."""
import socket
import struct

from security import UploadError


def scan_file(path, addr):
    if not addr:
        return
    try:
        if ":" in addr and not addr.startswith("/"):
            host, port = addr.rsplit(":", 1)
            s = socket.create_connection((host, int(port)), timeout=60)
        else:
            s = socket.socket(socket.AF_UNIX); s.settimeout(60); s.connect(addr)
        with s, open(path, "rb") as f:
            s.sendall(b"zINSTREAM\0")
            while chunk := f.read(64 * 1024):
                s.sendall(struct.pack(">I", len(chunk)) + chunk)
            s.sendall(struct.pack(">I", 0))
            reply = b""
            while not reply.endswith(b"\0") and (d := s.recv(4096)):
                reply += d
    except OSError:
        raise UploadError("Malware scanner unavailable; try again later.")
    text = reply.rstrip(b"\0").decode(errors="replace")
    if text.endswith("OK"):
        return
    if "FOUND" in text:
        raise UploadError("Upload rejected by the malware scanner.")
    raise UploadError("Malware scanner returned an error; try again later.")
