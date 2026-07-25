from pathlib import Path
import hashlib


def calculate_file_sha256(file_path: Path) -> str:
    """
    Calculates SHA256 hash of a file.

    Used for duplicate upload detection. Filename alone is not reliable because
    two files can share a name but contain different data.
    """
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()