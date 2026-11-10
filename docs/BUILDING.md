# 从源码构建无线麦 1.0.107

源码按 GPL-3.0-only 提供，来源见 legal/COPYRIGHT.md 和 apps/windows/rc003/ATTRIBUTION.md。第三方组件、模型和素材保留各自许可。

## 1. 准备 Nano 原生工作程序

在 Ubuntu/WSL 安装 Python 3.12+、CMake、Ninja、patch、MinGW-w64 POSIX GCC/G++。示例：

```sh
sudo apt-get install cmake ninja-build patch gcc-mingw-w64-x86-64-posix g++-mingw-w64-x86-64-posix
python3 apps/windows/rc003/build/nano/build-runtime.py
```

已下载发布源码附件时，可加 `--archive-dir third-party-source/nano` 使用附件中的源码归档。脚本校验归档后交叉编译 Windows x64 AVX2 工作程序，生成 `apps/windows/rc003/.build/nano-runtime/rc003-nano.exe`；不会下载语音模型。固定来源、SHA-256、补丁、编译参数及许可见 build/nano/。

## 2. Windows 桌面程序

安装 Python 3.12 x64、Visual Studio C++ Build Tools（包含Windows SDK）。在 Windows PowerShell 进入 `apps/windows/rc003`，执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
powershell -ExecutionPolicy Bypass -File build\build-candidate.ps1 -PythonExecutable .\.venv\Scripts\python.exe
```

构建脚本运行检查、编译第一方模块、收集 Qt 和其它运行依赖。输出在 dist/RemoteMicRC003。编译结果受编译器、Python补丁版本及依赖平台影响，不能承诺逐字节一致；发布时记录实际附件摘要。源码运行可设置 PYTHONPATH=src 并使用 `python -m ovb_rc003 --settings`，同样需要先准备 Nano 工作程序。

构建缓存、模型、个人配置和日志不提交 Git。普通源码包不包含这些文件；使用发布源码包中的第三方归档或脚本的固定下载地址恢复构建输入。

## 3. 公开分发

构建链历史上会获取官方 VB-CABLE 安装包；这不代表已获所有用途的再分发许可。当前GitHub CI设置 `RC003_PUBLIC_DISTRIBUTION=1`，PyInstaller不会把驱动ZIP收集进产物。本地公开构建也应先设置同一环境变量。公开应用ZIP须移除 `VBCABLE_Driver_Pack45.zip`，让用户自行从VB-Audio下载，或先取得适用的分发授权。不要改动原厂安装包或把驱动改称本项目GPL代码。

同时提供对应版本源码、Nano固定上游源码归档、完整第三方许可和校验文件。Qt对应源码见 legal/THIRD_PARTY_SOURCE.md。发布时附上应用ZIP、完整源码ZIP和SHA256SUMS.txt，并在GitHub Releases注明验证范围。
