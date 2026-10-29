#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

import requests


def load_config():
    path = Path(os.environ.get("OPENCODE_CONFIG", Path.home() / ".config/opencode/opencode.json"))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def provider_options(config):
    return (((config.get("provider") or {}).get("360-proxy") or {}).get("options") or {})


def api_key(config):
    for name in ("IMAGE_API_KEY", "OPENCODE_360_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "GLM_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value
    value = provider_options(config).get("apiKey")
    if value:
        return value
    raise SystemExit("image api key not found")


def api_base(config):
    base = os.environ.get("IMAGE_API_BASE") or provider_options(config).get("baseURL") or "https://api.360.cn/v1"
    return str(base).rstrip("/")


def cache_path(cache_dir, key):
    return Path(cache_dir) / f"{key}.json"


def download(url, timeout):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def save_image(content, out):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() == ".webp":
        from io import BytesIO
        from PIL import Image
        image = Image.open(BytesIO(content)).convert("RGB")
        image.save(out, format="WEBP", quality=88, method=6)
    else:
        out.write_bytes(content)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="")
    parser.add_argument("--prompt-file", default="")
    parser.add_argument("--model", default=os.environ.get("IMAGE_MODEL", "openai/gpt-image-2"))
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--quality", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--cache-dir", default=str(Path(".cache/image2")))
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    prompt = args.prompt_file and Path(args.prompt_file).read_text(encoding="utf-8") or args.prompt
    if not prompt.strip():
        raise SystemExit("prompt is empty")

    config = load_config()
    base = api_base(config)
    key = api_key(config)
    digest = hashlib.sha256(f"{args.model}\n{args.size}\n{prompt}".encode("utf-8")).hexdigest()
    cache_file = cache_path(args.cache_dir, digest)
    out = Path(args.out)

    if not args.no_cache and cache_file.exists():
        meta = json.loads(cache_file.read_text(encoding="utf-8"))
        cached = meta.get("file")
        if cached and Path(cached).exists():
            if args.json:
                print(json.dumps({**meta, "cached": True}, ensure_ascii=False, indent=2))
            else:
                print(cached)
            return

    payload = {"model": args.model, "prompt": prompt, "n": 1, "size": args.size}
    if args.quality:
        payload["quality"] = args.quality
    if args.dry_run:
        print(json.dumps({"endpoint": f"{base}/images/generations", "payload": {**payload, "prompt": prompt[:120] + ("..." if len(prompt) > 120 else "")}}, ensure_ascii=False, indent=2))
        return

    response = requests.post(
        f"{base}/images/generations",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=args.timeout,
    )
    response.raise_for_status()
    data = response.json()
    item = (data.get("data") or [{}])[0]
    if item.get("b64_json"):
        content = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        content = download(item["url"], args.timeout)
    else:
        raise SystemExit(f"image response has no b64_json/url: {str(data)[:400]}")

    saved = save_image(content, out)
    meta = {
        "file": str(saved),
        "model": data.get("model") or args.model,
        "requested_model": args.model,
        "size": data.get("size") or args.size,
        "quality": data.get("quality") or args.quality,
        "usage": data.get("usage") or {},
        "prompt": prompt,
        "hash": digest,
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps({**meta, "cached": False}, ensure_ascii=False, indent=2))
    else:
        print(saved)


if __name__ == "__main__":
    main()
