#!/usr/bin/env python3
"""下载轻量检测与分割模型包并安装到 runtime/models 目录。"""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import json
import os
import posixpath
import shutil
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


MMSEG_RAW_BASE = "https://raw.githubusercontent.com/open-mmlab/mmsegmentation/main/"
DEFAULT_MODEL_ROOT = "runtime/models"


@dataclass(frozen=True)
class SegConfigSpec:
    name: str
    config_relpath: str
    checkpoint_url: str
    target_class_ids: tuple[int, ...]


@dataclass(frozen=True)
class PackSpec:
    key: str
    version: str
    detector_name: str
    detector_url: str
    segmentor: SegConfigSpec
    note: str


SEGFORMER_B0 = SegConfigSpec(
    name="segformer_mit-b0_ade20k",
    config_relpath="configs/segformer/segformer_mit-b0_8xb2-160k_ade20k-512x512.py",
    checkpoint_url=(
        "https://download.openmmlab.com/mmsegmentation/v0.5/segformer/"
        "segformer_mit-b0_512x512_160k_ade20k/"
        "segformer_mit-b0_512x512_160k_ade20k_20210726_101530-8ffa8fda.pth"
    ),
    target_class_ids=(21,),
)

SEGFORMER_B1 = SegConfigSpec(
    name="segformer_mit-b1_ade20k",
    config_relpath="configs/segformer/segformer_mit-b1_8xb2-160k_ade20k-512x512.py",
    checkpoint_url=(
        "https://download.openmmlab.com/mmsegmentation/v0.5/segformer/"
        "segformer_mit-b1_512x512_160k_ade20k/"
        "segformer_mit-b1_512x512_160k_ade20k_20210726_112106-d70e859d.pth"
    ),
    target_class_ids=(21,),
)

PACKS: tuple[PackSpec, ...] = (
    PackSpec(
        key="nano-v8-b0",
        version="000101",
        detector_name="yolov8n",
        detector_url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt",
        segmentor=SEGFORMER_B0,
        note="Small baseline. Fast startup for CPU tests.",
    ),
    PackSpec(
        key="nano-v11-b0",
        version="000001",
        detector_name="yolo11n",
        detector_url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
        segmentor=SEGFORMER_B0,
        note="Recommended default. Lighter detector with the same B0 segmentor.",
    ),
    PackSpec(
        key="nano-v11-b1",
        version="000099",
        detector_name="yolo11n",
        detector_url="https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt",
        segmentor=SEGFORMER_B1,
        note="Higher segmentation quality candidate; still compact enough for validation.",
    ),
)


def _sha1_short(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _download_binary(url: str, dest: Path, timeout: int = 120, retries: int = 3) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(dest.parent)) as tmp:
                    shutil.copyfileobj(response, tmp)
                    tmp_path = Path(tmp.name)
            tmp_path.replace(dest)
            return
        except Exception as exc:  # pragma: no cover - network instability
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"failed to download binary after {retries} attempts: {url}") from last_error


def _cached_binary(url: str, cache_dir: Path, force: bool = False) -> Path:
    suffix = Path(url).name or "artifact.bin"
    cached = cache_dir / f"{_sha1_short(url)}-{suffix}"
    if force and cached.exists():
        cached.unlink()
    if cached.exists() and cached.stat().st_size > 0:
        return cached
    print(f"[download] {url}")
    _download_binary(url, cached)
    return cached


def _fetch_text(url: str, timeout: int = 60, retries: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - network instability
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(1.0 * attempt)
    raise RuntimeError(f"failed to download text after {retries} attempts: {url}") from last_error


def _extract_bases(config_text: str) -> list[str]:
    try:
        tree = ast.parse(config_text)
    except SyntaxError:
        return []

    def node_to_list(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, (ast.List, ast.Tuple)):
            values: list[str] = []
            for item in node.elts:
                values.extend(node_to_list(item))
            return values
        return []

    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "_base_":
                    return node_to_list(stmt.value)
    return []


def _normalize_relpath(path: str) -> str:
    normalized = posixpath.normpath(path)
    if normalized.startswith("../"):
        raise ValueError(f"invalid config path escaping root: {path}")
    return normalized.lstrip("./")


def _copy_mmseg_config_tree(config_relpath: str, output_dir: Path, cache_dir: Path, force: bool = False) -> None:
    queue = [_normalize_relpath(config_relpath)]
    seen: set[str] = set()

    while queue:
        relpath = queue.pop(0)
        if relpath in seen:
            continue
        seen.add(relpath)

        cache_file = cache_dir / relpath
        target_file = output_dir / relpath
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if force and target_file.exists():
            target_file.unlink()

        if not cache_file.exists() or force:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            url = f"{MMSEG_RAW_BASE}{relpath}"
            print(f"[download] {url}")
            text = _fetch_text(url)
            cache_file.write_text(text, encoding="utf-8")
        else:
            text = cache_file.read_text(encoding="utf-8")

        target_file.write_text(text, encoding="utf-8")

        for base_path in _extract_bases(text):
            candidate = base_path.split("mmseg::", 1)[-1] if base_path.startswith("mmseg::") else base_path
            base_rel = _normalize_relpath(posixpath.join(posixpath.dirname(relpath), candidate))
            queue.append(base_rel)


def _write_wrapper_config(dest: Path, config_relpath: str) -> None:
    rel = config_relpath.replace("\\", "/")
    wrapper = f"_base_ = ['./{rel}']\n"
    dest.write_text(wrapper, encoding="utf-8")


def _write_metadata(dest_dir: Path, pack: PackSpec) -> None:
    payload = {
        "pack_key": pack.key,
        "version": pack.version,
        "detector": {
            "name": pack.detector_name,
            "weights_url": pack.detector_url,
            "file": "det_model.pt",
        },
        "segmentor": {
            "name": pack.segmentor.name,
            "config_relpath": pack.segmentor.config_relpath,
            "checkpoint_url": pack.segmentor.checkpoint_url,
            "file": "seg_model.pt",
            "target_class_ids": list(pack.segmentor.target_class_ids),
        },
        "note": pack.note,
        "installed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (dest_dir / "model.meta.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _install_pack(pack: PackSpec, model_root: Path, cache_root: Path, force: bool = False) -> None:
    version_dir = model_root / pack.version
    version_dir.mkdir(parents=True, exist_ok=True)

    assets_cache = cache_root / "assets"
    config_cache = cache_root / "mmseg_configs"
    assets_cache.mkdir(parents=True, exist_ok=True)
    config_cache.mkdir(parents=True, exist_ok=True)

    det_cached = _cached_binary(pack.detector_url, assets_cache, force=force)
    seg_cached = _cached_binary(pack.segmentor.checkpoint_url, assets_cache, force=force)

    det_path = version_dir / "det_model.pt"
    seg_path = version_dir / "seg_model.pt"
    shutil.copy2(det_cached, det_path)
    shutil.copy2(seg_cached, seg_path)
    os.chmod(det_path, 0o644)
    os.chmod(seg_path, 0o644)
    _copy_mmseg_config_tree(pack.segmentor.config_relpath, version_dir, config_cache, force=force)
    _write_wrapper_config(version_dir / "mmseg_config.py", pack.segmentor.config_relpath)
    _write_metadata(version_dir, pack)

    print(f"[ok] installed pack={pack.key} version={pack.version} -> {version_dir}")


def _resolve_packs(selected: str) -> list[PackSpec]:
    if selected.strip().lower() == "all":
        return list(PACKS)
    requested = [item.strip() for item in selected.split(",") if item.strip()]
    indexed = {p.key: p for p in PACKS}
    packs: list[PackSpec] = []
    for key in requested:
        if key not in indexed:
            available = ", ".join(sorted(indexed))
            raise ValueError(f"unknown pack '{key}', available: {available}")
        packs.append(indexed[key])
    return packs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-root",
        default=DEFAULT_MODEL_ROOT,
        help="Model root directory, defaults to runtime/models",
    )
    parser.add_argument(
        "--packs",
        default="nano-v11-b0",
        help="Comma-separated pack keys or 'all'. Default: nano-v11-b0",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download all selected artifacts and overwrite cache.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available pack keys and exit.",
    )
    args = parser.parse_args()

    if args.list:
        for pack in PACKS:
            print(f"{pack.key:12s} version={pack.version} detector={pack.detector_name} seg={pack.segmentor.name}")
        return

    model_root = Path(args.model_root).resolve()
    cache_root = model_root / ".downloads"
    model_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    packs = _resolve_packs(args.packs)
    print(f"[info] model_root={model_root}")
    print(f"[info] packs={', '.join(p.key for p in packs)}")

    for pack in packs:
        _install_pack(pack, model_root=model_root, cache_root=cache_root, force=args.force)

    latest_version = max(int(p.version) for p in packs)
    print(f"[done] installed {len(packs)} pack(s). latest numeric version in selection={latest_version:06d}")
    print("[hint] set alert.segmentor_target_class_ids to [21] when using ADE20K-based packs")


if __name__ == "__main__":
    main()
