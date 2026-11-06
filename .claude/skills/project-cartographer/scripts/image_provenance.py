import hashlib
import json
from pathlib import Path


def record_generation(file, model, prompt_hash, cached=False):
    from PIL import Image
    file = Path(file)
    with Image.open(file) as image:
        if image.format not in {"WEBP", "PNG", "JPEG"}:
            raise ValueError("只接受文生图模型返回的位图")
        image.verify()
    receipt = {"source": "text-to-image", "model": model, "prompt_hash": prompt_hash,
               "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "cached": cached}
    Path(str(file) + ".generation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def generated_image(file):
    from PIL import Image
    file = Path(file)
    try:
        data = json.loads(Path(str(file) + ".generation.json").read_text())
        if not isinstance(data, dict):
            return False
        if data.get("source") != "text-to-image" or not data.get("model") or not data.get("prompt_hash"):
            return False
        if data.get("sha256") != hashlib.sha256(file.read_bytes()).hexdigest():
            return False
        with Image.open(file) as image:
            if image.format not in {"WEBP", "PNG", "JPEG"}:
                return False
            image.verify()
        return True
    except (OSError, ValueError, TypeError):
        return False
