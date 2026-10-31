#!/usr/bin/env python3
import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ROOT / "ui" / "data" / "projects.json"
CATALOG = ROOT / "catalog" / "manifest.json"
LOGO_DIR = ROOT / "ui" / "public" / "logos"
USER_AGENT = "mygoldmine-logo-fetch/1.0"
GITHUB_RE = re.compile(r"github\.com[:/]([^/]+)/([^/.#]+)", re.I)
GITLAB_RE = re.compile(r"gitlab\.com[:/]([^/]+)/([^/.#]+)", re.I)
IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF8", b"RIFF")


def slug(key):
    return re.sub(r"[^a-z0-9._-]+", "-", key.lower()).strip("-")


def catalog_urls():
    try:
        data = json.loads(CATALOG.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        key: item.get("url") or ""
        for key, item in (data.get("projects") or {}).items()
        if isinstance(item, dict)
    }


def logo_source(url):
    match = GITHUB_RE.search(url or "")
    if match:
        owner = match.group(1)
        return f"https://github.com/{owner}.png?size=80", owner, "github"
    match = GITLAB_RE.search(url or "")
    if match:
        owner = match.group(1)
        return f"https://gitlab.com/{owner}.png", owner, "gitlab"
    return "", "", ""


def download(url, dest, timeout, retries=2):
    last = ""
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
                content_type = (response.headers.get("content-type") or "").lower()
            if len(data) < 64:
                raise ValueError(f"image too small ({len(data)} bytes)")
            if not content_type.startswith("image/"):
                raise ValueError(f"unexpected content-type: {content_type}")
            if not data.startswith(IMAGE_MAGIC):
                raise ValueError("not a supported image")
            dest.parent.mkdir(parents=True, exist_ok=True)
            temp = dest.with_suffix(dest.suffix + ".tmp")
            temp.write_bytes(data)
            temp.replace(dest)
            return True, ""
        except Exception as exc:
            last = str(exc)
            if attempt < retries:
                time.sleep(0.6 * (attempt + 1))
    return False, last


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    data = json.loads(PROJECTS.read_text(encoding="utf-8"))
    projects = data.get("projects") or {}
    fallback = catalog_urls()
    tasks = []
    for key, project in projects.items():
        url = project.get("url") or fallback.get(key, "")
        source, owner, host = logo_source(url)
        if not source:
            project.pop("logo", None)
            project.pop("logo_source", None)
            project.pop("logo_owner", None)
            continue
        dest = LOGO_DIR / f"{slug(key)}.png"
        public = f"/logos/{dest.name}"
        if (
            dest.exists()
            and project.get("logo_source") == source
            and not args.force
        ):
            project["logo"] = public
            project["logo_source"] = source
            project["logo_owner"] = owner
            continue
        tasks.append((key, project, source, owner, host, dest, public))

    if args.limit:
        tasks = tasks[: args.limit]

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(download, source, dest, args.timeout): (key, project, source, owner, host, dest, public)
            for key, project, source, owner, host, dest, public in tasks
        }
        for future in as_completed(futures):
            key, project, source, owner, host, dest, public = futures[future]
            ok, error = future.result()
            if ok:
                project["logo"] = public
                project["logo_source"] = source
                project["logo_owner"] = owner
                results.append((key, "ok", ""))
            else:
                project.pop("logo", None)
                project.pop("logo_source", None)
                project.pop("logo_owner", None)
                results.append((key, "failed", error))

    data["projects"] = projects
    temp = PROJECTS.with_suffix(PROJECTS.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(PROJECTS)

    failed = [item for item in results if item[1] == "failed"]
    print(json.dumps({
        "projects": len(projects),
        "fetched": len([item for item in results if item[1] == "ok"]),
        "failed": len(failed),
        "cached": len(projects) - len(tasks) - len(failed),
        "logo_dir": str(LOGO_DIR),
        "errors": failed[:10],
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
