"""Build the Windows Nano worker from pinned upstream source, on Linux/WSL."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
URLS = {
    "fun-asr-source.tar.gz": "https://api.github.com/repos/QwenAudio/Fun-ASR/tarball/c0a20e2",
    "llama-source.tar.gz": "https://api.github.com/repos/ggml-org/llama.cpp/tarball/8086439a4cea94c71a5dfb8fe4ad1546aebd640f",
}

def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def sources(archive_dir, metadata):
    archive_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, expected in metadata["source_archives"].items():
        target = archive_dir / name
        if not target.is_file():
            temporary = target.with_suffix(target.suffix + ".part")
            try:
                request = urllib.request.Request(URLS[name], headers={"User-Agent": "RemoteMic-source-build"})
                with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
                if digest(temporary) != expected:
                    raise ValueError("source archive checksum mismatch: " + name)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
        if digest(target) != expected:
            raise ValueError("source archive checksum mismatch: " + name)
        result[name] = target
    return result

def extract(archive, target):
    target.mkdir(parents=True, exist_ok=False)
    with tarfile.open(archive, "r:gz") as bundle:
        bundle.extractall(target, filter="data")
    roots = list(target.iterdir())
    if len(roots) != 1 or not roots[0].is_dir():
        raise ValueError("unexpected source archive layout")
    return roots[0]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=ROOT / ".build/nano-source")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--verify-only", action="store_true", help="verify archives without compiling")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    metadata = json.loads((HERE / "native-build.json").read_text())
    archives = sources(args.archive_dir.resolve(), metadata)
    if args.verify_only:
        print("Nano source archives: SHA-256 verified")
        return
    for tool in ("cmake", "ninja", "patch", "x86_64-w64-mingw32-gcc-posix", "x86_64-w64-mingw32-g++-posix"):
        if not shutil.which(tool):
            raise RuntimeError("required Linux/WSL build tool is missing: " + tool)
    work = ROOT / ".build/nano-rebuild"
    work.mkdir(parents=True, exist_ok=True)
    # Source directories are disposable copies of the verified archives.
    for name in ("fun", "llama", "build"):
        path = work / name
        if path.exists():
            shutil.rmtree(path)
    fun = extract(archives["fun-asr-source.tar.gz"], work / "fun")
    llama = extract(archives["llama-source.tar.gz"], work / "llama")
    shutil.copy2(HERE / "rc003-nano.cpp", fun / "runtime/llama.cpp/funasr-cli/funasr-cli.cpp")
    subprocess.run(["patch", "-p1", "-i", str(HERE / "mingw-headers.patch")], cwd=llama, check=True)
    build = work / "build"
    subprocess.run(["cmake", "-S", str(fun / "runtime/llama.cpp"), "-B", str(build), "-G", "Ninja",
        "-DCMAKE_TOOLCHAIN_FILE=" + str(HERE / "toolchain.cmake"),
        "-DFETCHCONTENT_SOURCE_DIR_LLAMA=" + str(llama), "-DCMAKE_BUILD_TYPE=Release",
        "-DGGML_NATIVE=OFF", "-DGGML_OPENMP=OFF", "-DGGML_AVX=ON", "-DGGML_AVX2=ON",
        "-DGGML_FMA=ON", "-DGGML_F16C=ON"], check=True)
    subprocess.run(["cmake", "--build", str(build), "--target", "llama-funasr-cli", "-j", str(args.jobs)], check=True)
    output = ROOT / ".build/nano-runtime/rc003-nano.exe"
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(build / "bin/llama-funasr-cli.exe", output)
    (output.parent / "build-receipt.json").write_text(json.dumps({
        "source_archives": metadata["source_archives"], "binary_sha256": digest(output),
        "compiler": subprocess.check_output(["x86_64-w64-mingw32-g++-posix", "--version"], text=True).splitlines()[0],
    }, indent=2) + "\n")
    print("Built Windows Nano worker: " + str(output))

if __name__ == "__main__":
    main()
