"""Prepare local GitHub release attachments; never uploads or changes Git history."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "apps/windows/rc003"
RELEASE_NOTES = APP / "release-notes/1.0.107.md"
PRIVATE_PREFIXES = (".codex/", ".build/", ".git/", "dist/")
SECRET_PATTERNS = (
    re.compile(rb"(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(rb"\bAKIA[A-Z0-9]{16}\b"),
)

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def source_files():
    result = subprocess.run(["git", "-c", "safe.directory=" + str(ROOT), "ls-files",
        "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, capture_output=True, check=True)
    paths = sorted(set(result.stdout.decode("utf-8").rstrip("\0").split("\0")))
    files = []
    for name in paths:
        if not name or name.startswith(PRIVATE_PREFIXES):
            continue
        path = ROOT / name
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError("Review symlink before publishing: " + name)
        if path.name == ".env" or path.name.startswith(".env.") and path.suffix not in (".example", ".sample"):
            raise ValueError("Review environment file before publishing: " + name)
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            raise ValueError("Potential credential detected; inspect locally: " + name)
        if str(ROOT).encode() in data:
            raise ValueError("Personal path detected; inspect locally: " + name)
        files.append((name, path))
    return files

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    version = (APP / "src/ovb_rc003/VERSION").read_text().strip()
    if version != "1.0.107":
        raise ValueError("This release recipe is pinned to 1.0.107")
    if not args.portable.is_file():
        raise FileNotFoundError(args.portable)
    files = source_files()
    meta = json.loads((APP / "build/nano/native-build.json").read_text())
    archives = APP / ".build/nano-source"
    for name, expected in meta["source_archives"].items():
        if sha(archives / name) != expected:
            raise ValueError("Nano source archive mismatch: " + name)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    prefix = "RemoteMicRC003-" + version
    source = output / (prefix + "-source.zip")
    with zipfile.ZipFile(source, "x", zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
        for name, path in files:
            bundle.write(path, prefix + "-source/" + name)
        for name in meta["source_archives"]:
            bundle.write(archives / name, prefix + "-source/third-party-source/nano/" + name)
    portable = output / (prefix + "-portable-unsigned.zip")
    omitted = []
    with zipfile.ZipFile(args.portable) as origin, zipfile.ZipFile(portable, "x", zipfile.ZIP_DEFLATED, compresslevel=1) as bundle:
        roots = {i.filename.split("/")[0] for i in origin.infolist() if "/" in i.filename}
        if len(roots) != 1:
            raise ValueError("Unexpected portable archive layout")
        root = roots.pop()
        for info in origin.infolist():
            relative = info.filename.partition("/")[2]
            if info.is_dir():
                continue
            if info.filename.lower().endswith("vbcable_driver_pack45.zip"):
                omitted.append(relative)
                continue
            # Refresh release notices; application binaries are copied unchanged.
            if relative.startswith("说明与许可/"):
                continue
            bundle.writestr(info.filename, origin.read(info))
        for name in ("LICENSE.md", "COPYRIGHT.md", "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_SOURCE.md", "ASSET_LICENSES.md"):
            bundle.write(ROOT / name, root + "/说明与许可/" + name)
        bundle.write(RELEASE_NOTES, root + "/说明与许可/版本说明.md")
        bundle.write(APP / "ATTRIBUTION.md", root + "/说明与许可/ATTRIBUTION.md")
        bundle.write(APP / "installer/readme-portable-rc003.txt", root + "/说明与许可/使用说明.txt")
        for base in (ROOT / "THIRD_PARTY_LICENSES", APP / "build/nano"):
            for path in sorted(base.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    bundle.write(path, root + "/说明与许可/" + base.name + "/" + path.relative_to(base).as_posix())
    sums = "".join(sha(path) + "  " + path.name + "\n" for path in (portable, source))
    (output / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
    (output / "发布说明.md").write_text(RELEASE_NOTES.read_text(), encoding="utf-8")
    (output / "上传步骤.md").write_text("在 https://github.com/WuYuStar/vibenano/releases 创建对应版本的预发布，使用发布说明.md作为正文，并同时上传应用ZIP、源码ZIP和SHA256SUMS.txt。\n", encoding="utf-8")
    (output / "source-file-list.txt").write_text("\n".join(name for name, _ in files) + "\n", encoding="utf-8")
    report = {"version": version, "source_files": len(files), "credentials_scan": "no configured high-confidence pattern found",
        "excluded_private_prefixes": PRIVATE_PREFIXES, "removed_vendor_files": omitted,
        "binary_runtime_tests": "not run; maintainer requested no additional package tests", "uploaded": False}
    (output / "PREPARATION.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **report}, ensure_ascii=False))

if __name__ == "__main__":
    main()
