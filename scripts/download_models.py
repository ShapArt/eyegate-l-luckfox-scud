#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

MODELS = {
    "yunet": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


def download_model(name: str, target_dir: Path) -> Path:
    url = MODELS[name]
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / url.split("/")[-1]
    if dest.exists():
        print(f"[skip] {dest} already exists")
        return dest
    print(f"[download] {name} -> {dest}")
    urlretrieve(url, dest)  # nosec - trusted model URLs
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download YuNet + SFace models into ./models/"
    )
    parser.add_argument(
        "--dir", type=Path, default=Path("models"), help="Destination directory"
    )
    args = parser.parse_args()
    for name in MODELS:
        download_model(name, args.dir)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
