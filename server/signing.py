"""Ed25519 catalog signing. Console clients embed the public key and refuse unsigned/forged catalogs."""
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def generate():
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                             serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return seed.hex(), pub


def sign_catalog(seed_hex, platform, lines, now=None):
    """Body = '#ts', '#plat' headers + rows. Appends '#sig<TAB>hex' over the exact body bytes."""
    body = f"#ts\t{int(now or time.time())}\n#plat\t{platform}\n" + "".join(l + "\n" for l in lines)
    sig = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex)).sign(body.encode())
    return body + "#sig\t" + sig.hex() + "\n"
