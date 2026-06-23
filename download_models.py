#!/usr/bin/env python3
"""
Download helper for shared models used by Vella-Server.

Downloads:
 - Faster-Whisper `base.en` -> models/models--Systran--faster-whisper-base.en
 - Faster-Whisper `medium.en` -> models/models--Systran--faster-whisper-medium.en
 - Faster-Whisper `large-v3-turbo` -> models/models--deepdml--faster-whisper-large-v3-turbo-ct2
 - Kokoro ONNX + voices bundle -> models/kokoro/

Usage:
 python Vella/download_models.py [--models base|medium|turbo|all] [--no-kokoro] [--dry-run]

By default the script performs a dry-run; omit `--dry-run` to actually download.
"""

from pathlib import Path
import sys
import os
import argparse


def safe_import(name: str):
    try:
        module = __import__(name)
        return module
    except Exception:
        return None


def download_whisper(model_name: str, out_dir: Path, dry_run: bool = True):
    try:
        fw = __import__("faster_whisper")
        download_model = getattr(fw, "download_model")
    except Exception:
        print("faster_whisper is not installed in this Python environment.")
        print("Install it with: pip install faster-whisper")
        raise

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"-> Will download Faster-Whisper '{model_name}' into: {out_dir}")
    if dry_run:
        print("   (dry-run) skipping actual download")
        return

    path = download_model(model_name, output_dir=str(out_dir))
    print(f"   Download finished: {path}")


def download_file(url: str, dest: Path, dry_run: bool = True):
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"-> Skipping {dest.name} (already exists)")
        return

    print(f"-> Downloading {dest.name} from {url}")
    if dry_run:
        print("   (dry-run) skipping actual download")
        return

    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"   Saved {dest}")


def download_kokoro(models_dir: Path, dry_run: bool = True):
    kokoro_dir = models_dir / "kokoro"
    kokoro_dir.mkdir(parents=True, exist_ok=True)

    files = [
        (
            "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
            kokoro_dir / "kokoro-v1.0.onnx",
        ),
        (
            "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
            kokoro_dir / "voices-v1.0.bin",
        ),
    ]

    for url, dest in files:
        download_file(url, dest, dry_run=dry_run)


def parse_args():
    p = argparse.ArgumentParser(description="Download Whisper (faster-whisper) models and Kokoro assets")
    p.add_argument("--models", choices=("base", "medium", "turbo", "small", "all"), default="all",
                   help="Which Whisper models to download")
    p.add_argument("--no-kokoro", action="store_true", help="Skip downloading Kokoro files")
    p.add_argument("--dry-run", action="store_true", help="Show what would be downloaded (default)")
    p.add_argument("--output", type=str, default=None, help="Optional models output directory")
    return p.parse_args()


def main():
    args = parse_args()

    # Resolve models directory relative to repository root (two levels up from this file)
    default_models_dir = Path(__file__).resolve().parents[1] / "models"
    models_dir = Path(args.output).expanduser().resolve() if args.output else default_models_dir
    print(f"Models directory: {models_dir}")

    # Ensure folder exists for dry-run visibility
    models_dir.mkdir(parents=True, exist_ok=True)

    do_base = args.models in ("base", "all")
    do_medium = args.models in ("medium", "all")
    do_turbo = args.models in ("turbo", "all")
    do_small = args.models in ("small", "all")

    any_fail = False

    try:
        if do_base:
            download_whisper("base.en", models_dir / "models--Systran--faster-whisper-base.en", dry_run=args.dry_run)
        if do_medium:
            download_whisper("medium.en", models_dir / "models--Systran--faster-whisper-medium.en", dry_run=args.dry_run)
        if do_small:
            download_whisper("small.en", models_dir / "models--Systran--faster-whisper-small.en", dry_run=args.dry_run)
        if do_turbo:
            download_whisper("deepdml/faster-whisper-large-v3-turbo-ct2", models_dir / "models--deepdml--faster-whisper-large-v3-turbo-ct2", dry_run=args.dry_run)
    except Exception as e:
        print(f"⚠️ Whisper download step failed: {e}")
        any_fail = True

    if not args.no_kokoro:
        try:
            download_kokoro(models_dir, dry_run=args.dry_run)
        except Exception as e:
            print(f"⚠️ Kokoro download step failed: {e}")
            any_fail = True

    if any_fail:
        print("Completed with warnings. Check output above for errors.")
        sys.exit(2)

    print("All requested actions completed.")


if __name__ == "__main__":
    main()