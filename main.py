#!/usr/bin/env python3
"""news-image-20261122 entrypoint.

Validates the bundled front-page image (entry.png, a JPEG) and copies it
byte-identical to /output/entry.png. Standard library only, no network.
Deterministic: both runs write the same bytes.
"""
import hashlib
import os
import struct
import sys

MAX_BYTES = 1048576          # 1 MiB
MAX_DIMENSION = 1024

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "entry.png")


def fail(message):
    print("main.py: ERROR: " + message, file=sys.stderr)
    sys.exit(1)


def read_source():
    if not os.path.isfile(SOURCE):
        fail("bundled image not found: " + SOURCE)
    with open(SOURCE, "rb") as handle:
        data = handle.read()
    if len(data) == 0:
        fail("bundled image is empty")
    if len(data) > MAX_BYTES:
        fail("bundled image is %d bytes, over the 1 MiB cap" % len(data))
    return data


def jpeg_dimensions(data):
    """Parse width/height from the first SOF marker of a JPEG."""
    if data[0:3] != b"\xff\xd8\xff":
        fail("not a JPEG: bad SOI marker")
    pos = 2
    while pos + 9 < len(data):
        if data[pos] != 0xFF:
            fail("JPEG parse error at offset %d" % pos)
        marker = data[pos + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            pos += 2
            continue
        if pos + 4 > len(data):
            fail("JPEG truncated inside a segment header")
        length = struct.unpack(">H", data[pos + 2:pos + 4])[0]
        if length < 2 or pos + 2 + length > len(data):
            fail("JPEG segment overruns the file")
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height = struct.unpack(">H", data[pos + 5:pos + 7])[0]
            width = struct.unpack(">H", data[pos + 7:pos + 9])[0]
            return width, height
        pos += 2 + length
    fail("no JPEG start-of-frame marker found")


def png_dimensions(data):
    """Parse width/height from a PNG IHDR chunk."""
    if data[0:8] != b"\x89PNG\r\n\x1a\n":
        fail("not a PNG: bad signature")
    if len(data) < 24 or data[12:16] != b"IHDR":
        fail("PNG has no IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def validate(data):
    """Check format, wholeness and dimensions; return (kind, width, height)."""
    if data[0:3] == b"\xff\xd8\xff":
        if data[-2:] != b"\xff\xd9":
            fail("JPEG is not whole: missing end-of-image marker")
        width, height = jpeg_dimensions(data)
        kind = "JPEG"
    elif data[0:8] == b"\x89PNG\r\n\x1a\n":
        if b"IEND" not in data[-12:]:
            fail("PNG is not whole: missing IEND chunk")
        width, height = png_dimensions(data)
        kind = "PNG"
    else:
        fail("bundled image is neither JPEG nor PNG (leading bytes %s)"
             % data[:8].hex())
    if width <= 0 or height <= 0:
        fail("image has non-positive dimensions %dx%d" % (width, height))
    if width > MAX_DIMENSION or height > MAX_DIMENSION:
        fail("image is %dx%d, over the 1024x1024 cap" % (width, height))
    return kind, width, height


def main():
    data = read_source()
    kind, width, height = validate(data)
    digest = hashlib.sha256(data).hexdigest()

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")
    with open(out_path, "wb") as handle:
        handle.write(data)

    with open(out_path, "rb") as handle:
        written = handle.read()
    if written != data:
        fail("output differs from the bundled image")
    if hashlib.sha256(written).hexdigest() != digest:
        fail("output sha256 mismatch")

    print("main.py: wrote %s (%s, %dx%d, %d bytes, sha256 %s) to %s"
          % (out_path, kind, width, height, len(data), digest, out_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
