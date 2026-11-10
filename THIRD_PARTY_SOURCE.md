# Third-party corresponding source

Release status: READY

The Windows binary bundles the open-source Qt for Python 6.11.1 runtime. The
application source is already available in this GPL-3.0-only repository, but a
formal binary release must also keep the exact Qt and PySide/Shiboken
corresponding source available from a location controlled by this project.

## Required source archives

### Qt 6.11.1

- File: `qt-everywhere-src-6.11.1.tar.xz`
- Official source: <https://download.qt.io/official_releases/qt/6.11/6.11.1/single/qt-everywhere-src-6.11.1.tar.xz>
- Size: 1,017,723,080 bytes
- SHA-256: `252acef8c5ae68074d91cadba2ee4a83465051bbb970dd26e8f0daa0f3904e03`
- Project-controlled release URL: <https://github.com/WuYuStar/vibenano/releases/download/third-party-source-qt-6.11.1/qt-everywhere-src-6.11.1.tar.xz>

### Qt for Python / PySide6 6.11.1

- File: `pyside-setup-everywhere-src-6.11.1.tar.xz`
- Official source: <https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/pyside-setup-everywhere-src-6.11.1.tar.xz>
- Size: 17,963,432 bytes
- SHA-256: `6ffd9835bb0dd2c56f061d62f1616bb1707cfc0202b80e3165d6be087f3965e2`
- Project-controlled release URL: <https://github.com/WuYuStar/vibenano/releases/download/third-party-source-qt-6.11.1/pyside-setup-everywhere-src-6.11.1.tar.xz>

## Distribution statement

The Windows build installs the official `PySide6-Essentials==6.11.1` and
`shiboken6==6.11.1` PyPI wheels and does not patch their source. PyInstaller
keeps Qt as replaceable DLLs and QML/plugin files under the application's
`程序文件/PySide6` directory rather than statically linking them into the main
executable.

The upstream project originally recorded its source delivery on 2026-09-01.
VibeNano mirrors these exact, unmodified source archives under its own
`third-party-source-qt-6.11.1` release. SHA-256 is checked before upload.
Official Qt URLs remain recorded as provenance. The VibeNano binary release
is published only after both mirror assets have been uploaded successfully.

## 1.0.107 Nano corresponding source

The `RemoteMicRC003-1.0.107-source.zip` release attachment includes the current
application source, `build/nano/` recipe, modified worker and license records,
plus `third-party-source/nano/fun-asr-source.tar.gz` and `llama-source.tar.gz`.
Exact archive SHA-256 values and revisions are in
`apps/windows/rc003/build/nano/native-build.json`. They must accompany the
portable binary release. Model weights remain separately downloaded and are
not substituted for implementation source. The existing Qt/PySide source
archives above remain required and must remain publicly downloadable.
