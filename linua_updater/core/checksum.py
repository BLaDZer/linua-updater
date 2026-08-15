import hashlib
import os

SUPPORTED_CHECKSUMS = ("sha256", "sha1", "md5")

_CHUNK_SIZE = 1024 * 1024


def verify_file_checksums(file_path, checksums):
    if not checksums:
        return []
    wanted = []
    for alg in SUPPORTED_CHECKSUMS:
        value = checksums.get(alg)
        if value is None:
            continue
        expected = str(value).strip()
        if expected:
            wanted.append((alg, expected))
    if not wanted:
        return []
    if not os.path.isfile(file_path):
        return ["Checksum verification failed: file not found"]
    hashers = [(alg, expected, hashlib.new(alg)) for alg, expected in wanted]
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(_CHUNK_SIZE)
                if not chunk:
                    break
                for _, _, hasher in hashers:
                    hasher.update(chunk)
    except OSError:
        return ["Checksum verification failed: file not found"]
    errors = []
    for alg, expected, hasher in hashers:
        actual = hasher.hexdigest()
        if actual.lower() != expected.lower():
            errors.append(f"Checksum mismatch ({alg}): expected {expected}, got {actual}")
    return errors
