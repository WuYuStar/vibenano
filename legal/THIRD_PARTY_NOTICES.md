# Third-party notices

This repository is licensed as `GPL-3.0-only`. The Windows binary also carries
the components listed below under their own licenses. Full license texts shipped
with the installer and portable archive are under `THIRD_PARTY_LICENSES/`.
Corresponding-source information for Qt for Python is recorded in
`THIRD_PARTY_SOURCE.md`.

## 1.0.107 public release packaging

The public release ZIP excludes the VB-CABLE installer. Historical build and
local-use bundles may contain its unmodified Basic ZIP; those are not the public
release artifact. Users obtain VB-CABLE directly from https://vb-audio.com/Cable/.
The vendor package readme permits unchanged copying but restricts integration
into other installation procedures; the vendor's current distribution terms at
https://shop.vb-audio.com/en/content/3-Terms-of-use describe distributor licensing.
This project does not assume a blanket redistribution grant from "Donationware".

Nano fixed upstream source archives, the modified worker, build recipe, patches
and complete Apache/MIT/compiler-runtime notices accompany the 1.0.107 source
release. Their exact hashes are recorded in build/nano/native-build.json.

## RC003 1.0.107 source configuration

The local speech engine is now exclusively Fun-ASR-Nano, with the existing
CPU-native runtime and separately downloaded GGUF model. Retired Whisper,
Paraformer and Qwen Python engines are excluded from the new build definition.
Their historical notices below remain for earlier distributions; this source
change neither removes installed packages nor produces a new binary release.

### HTTPS model downloads and cache locking

- Package: `requests==2.34.2`; license: Apache-2.0.
  Existing license and NOTICE:
  `THIRD_PARTY_LICENSES/runtime-1.0.104/requests-2.34.2/requests-2.34.2.dist-info/licenses/`.
- Package: `filelock==4.2.9`; license: MIT.
  Existing license:
  `THIRD_PARTY_LICENSES/runtime-1.0.104/filelock-4.2.9/filelock-4.2.9.dist-info/licenses/LICENSE`.

These lightweight dependencies handle HTTPS transfers and shared-cache locking;
no Python machine-learning framework is required for Nano recognition.

## Frozen Python and audio runtime

The 1.0.104 candidate uses the supplied CPython 3.12.14 runtime. Its OpenSSL
pair is taken from that interpreter's DLL directory, avoiding identically named
libraries on unrelated applications' PATHs. Its SSLContext policy PEM is
preserved with the runtime data; TLS verification is not disabled.

### CPython 3.12.10 (historical); 3.12.14 in the 1.0.104 candidate

- Project: CPython
- Source: <https://www.python.org/downloads/source/>
- License: Python Software Foundation License
- Distributed form: Python interpreter DLLs and standard-library modules
- License text: `THIRD_PARTY_LICENSES/Python-3.12/LICENSE.txt`

### OpenSSL 3

- Project: OpenSSL
- Source: <https://github.com/openssl/openssl>
- License: Apache License 2.0
- Distributed form: OpenSSL runtime DLLs brought in by CPython and Qt
- License text: `THIRD_PARTY_LICENSES/OpenSSL-3/LICENSE.txt`

The exact OpenSSL file versions are checked from the final Windows artifact;
they may differ between the CPython and Qt runtime trees.

### PySide6 Essentials, Shiboken6 and Qt 6.11.1

- Packages: `PySide6-Essentials==6.11.1`, `shiboken6==6.11.1`
- Projects: Qt for Python and Qt
- Sources: <https://code.qt.io/cgit/pyside/pyside-setup.git/> and
  <https://code.qt.io/cgit/qt/qt5.git/>
- License choices published by Qt for Python: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`
- Distributed form: PySide/Shiboken extension modules, replaceable Qt DLLs,
  plugins and QML modules in the one-directory application
- License texts: `THIRD_PARTY_LICENSES/Qt-PySide6-6.11.1/`

This project uses the open-source Qt for Python distribution and does not claim
a commercial Qt license. The application itself is GPL-3.0-only. Exact source
archives, hashes and the still-required project-controlled source location are
recorded in `THIRD_PARTY_SOURCE.md`.

### NumPy

- Package: `numpy==2.4.3`
- Source: <https://github.com/numpy/numpy>
- License expression: `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`
- Distributed form: Python modules and native numerical libraries
- Main license text: `THIRD_PARTY_LICENSES/NumPy-2.4.3/LICENSE.txt`

PyInstaller also preserves NumPy's complete package license tree under
`程序文件/numpy-2.4.3.dist-info/licenses/` in current frozen applications.

### faster-whisper

- Package: `faster-whisper==1.2.1`
- Source: <https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1>
- License: MIT
- Distributed form: Python modules and package metadata in the frozen local
  speech provider
- License text: `THIRD_PARTY_LICENSES/faster-whisper-1.2.1/LICENSE.txt`

### CTranslate2

- Package: `ctranslate2==4.8.5`
- Source: <https://github.com/OpenNMT/CTranslate2/tree/v4.8.5>
- License: MIT
- Distributed form: Python modules, the native Python extension, and native DLLs
  shipped by the pinned Windows x64 wheel
- License text: `THIRD_PARTY_LICENSES/ctranslate2-4.8.5/LICENSE.txt`

### Hugging Face Tokenizers

- Package: `tokenizers==0.23.3`
- Source: <https://github.com/huggingface/tokenizers/tree/v0.23.3>
- License: Apache License 2.0
- Distributed form: Python modules and the native tokenizer extension
- License text: `THIRD_PARTY_LICENSES/tokenizers-0.23.3/LICENSE.txt`

### ONNX Runtime

- Package: `onnxruntime==1.31.1`
- Source: <https://github.com/microsoft/onnxruntime/tree/v1.31.1>
- License: MIT
- Distributed form: Python modules, the native Python extension, runtime and
  provider DLLs, and package notices from the pinned Windows x64 wheel
- License text: `THIRD_PARTY_LICENSES/onnxruntime-1.31.1/LICENSE.txt`

ONNX Runtime remains required when `faster_whisper` is imported even though this
application supplies a NumPy PCM array and disables faster-whisper's VAD filter.

### PyAV

- Package: `av==19.0.2`
- Source: <https://github.com/PyAV-Org/PyAV/tree/v19.0.2>
- License: BSD-3-Clause
- Distributed form: Python modules, native Python extensions, and the sibling
  `av.libs` native codec/runtime DLL payload from the pinned Windows x64 wheel
- License text: `THIRD_PARTY_LICENSES/av-19.0.2/LICENSE.txt`

PyAV remains required when `faster_whisper` is imported; using direct NumPy PCM
does not remove that module-import dependency.

### Hugging Face Hub

- Package: `huggingface-hub==0.36.2`
- Source: <https://github.com/huggingface/huggingface_hub/tree/v0.36.2>
- License: Apache License 2.0
- Distributed form: Python modules and package metadata used for first-use model
  download and subsequent cached model loading
- License text: `THIRD_PARTY_LICENSES/huggingface-hub-0.36.2/LICENSE.txt`

The six direct speech packages resolve additional Python dependencies, and some
native wheels redistribute additional runtime or codec libraries, including
PyAV's `av.libs` payload. The final frozen Windows artifact, including its
package metadata and native-library directories, is the source of truth for the
exact transitive closure actually distributed; this direct-pin list is not an
exhaustive transitive inventory.

### Separately downloaded faster-whisper models

No Whisper model weights or model-repository snapshots are committed to this
repository or bundled into the frozen application. On first use, the selected
`tiny`, `base`, or `small` model is downloaded as user data beneath the
application configuration root in `models/faster-whisper`; later runs can load
the cached copy without another download.

The corresponding Systran model repositories and cards declare the MIT license:

- <https://huggingface.co/Systran/faster-whisper-tiny>
- <https://huggingface.co/Systran/faster-whisper-base>
- <https://huggingface.co/Systran/faster-whisper-small>

Those cards identify the original OpenAI Whisper models and their model cards as
additional provenance. Downloaded models remain separate from the package and
native-library notices above.

### Paraformer and model download runtime (1.0.104 candidate)

The packaged application includes both local recognition engines; native
models are imported only inside the selected recognition child process.
Model weights remain separately downloaded user data. The 1.0.104 candidate
adds these direct pins from `requirements-paraformer.txt`:

- `funasr==1.3.1` — MIT; <https://github.com/modelscope/FunASR>
- `torch==2.9.1+cpu` — BSD-3-Clause with bundled third-party components;
  <https://github.com/pytorch/pytorch>
- `torchaudio==2.9.1+cpu` — its wheel's BSD-style license;
  <https://github.com/pytorch/audio>
- `modelscope==1.40.2` and `modelscope-hub==0.6.1` — Apache-2.0;
  <https://github.com/modelscope/modelscope>
- `librosa==1.0.0` — ISC; <https://github.com/librosa/librosa>
- `kaldiio==2.18.1` — MIT; <https://github.com/nttcslab-sp/kaldiio>

The runtime dependency closure (85 installed distributions) and 134 license,
notice and copyright files extracted from their wheels are preserved under
`THIRD_PARTY_LICENSES/runtime-1.0.104/`, with exact versions and source metadata
in `inventory.json`. This supplements the existing notices, including the
PyInstaller bootloader license exception. Model downloads use the same caches
for the settings buttons and automatic first use; they do not upload audio.

The separate Paraformer checkpoint, pinned at revision `v2.0.4`, is:
<https://modelscope.cn/models/iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online>.
Its model card and <https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE>
describe model terms separately from FunASR's code license. Weights are not
committed or included in the portable application.

### python-sounddevice and PortAudio

- Package: `sounddevice==0.5.5`
- Source: <https://github.com/spatialaudio/python-sounddevice>
- License: MIT
- License text: `THIRD_PARTY_LICENSES/sounddevice-0.5.5/LICENSE.txt`
- Runtime library: PortAudio
- PortAudio source: <https://github.com/PortAudio/portaudio>
- PortAudio license: MIT
- PortAudio license text: `THIRD_PARTY_LICENSES/PortAudio/LICENSE.txt`

Only the normal non-ASIO PortAudio DLL is required and distributed. The
separately supplied ASIO-enabled DLL is excluded from the PyInstaller output.

### pywinrt projections

The following packages are all version 3.2.1 and licensed under MIT:

- `winrt-runtime==3.2.1`
- `winrt-Windows.Devices.Bluetooth==3.2.1`
- `winrt-Windows.Devices.Bluetooth.GenericAttributeProfile==3.2.1`
- `winrt-Windows.Devices.Enumeration==3.2.1`
- `winrt-Windows.Storage.Streams==3.2.1`
- `winrt-Windows.Foundation==3.2.1`
- `winrt-Windows.Foundation.Collections==3.2.1`

Source: <https://github.com/pywinrt/pywinrt>. License text:
`THIRD_PARTY_LICENSES/pywinrt-3.2.1/LICENSE.txt`.

### Frida Python bindings and Frida Gadget

- Package and release: `frida==17.15.3`
- Project: Frida
- Source: <https://github.com/frida/frida>
- License: wxWindows Library Licence, Version 3.1
- License text: `THIRD_PARTY_LICENSES/Frida-17.15.3/COPYING.txt`
- Gadget asset: `frida-gadget-17.15.3-windows-x86_64.dll.xz`
- Gadget SHA-256: `B566D70189B6D551AD8F4E0BEA24DE08A3D4C0F559BB35B2BDB67D45182240C2`

The Gadget archive is not committed to this repository. Candidate builds fetch
the pinned official asset and verify its hash before freezing it. Runtime
verifies the archive again before use.

### Windows UI Automation support

- Package: `uiautomation==2.0.29`
- Project: Python-UIAutomation-for-Windows
- Source: <https://github.com/yinkaisheng/Python-UIAutomation-for-Windows>
- License: Apache License 2.0
- License text: `THIRD_PARTY_LICENSES/uiautomation-2.0.29/LICENSE.txt`

- Package: `comtypes==1.4.16`
- Source: <https://github.com/enthought/comtypes>
- License: MIT
- License text: `THIRD_PARTY_LICENSES/comtypes-1.4.16/LICENSE.txt`

### Supporting Python packages

- `cffi==2.1.1`, MIT-0:
  `THIRD_PARTY_LICENSES/cffi-2.1.1/LICENSE.txt`
- `pycparser==3.0`, BSD-3-Clause:
  `THIRD_PARTY_LICENSES/pycparser-3.0/LICENSE.txt`
- `typing_extensions==4.16.0`, PSF-2.0:
  `THIRD_PARTY_LICENSES/typing_extensions-4.16.0/LICENSE.txt`

These packages are included only when reached by the frozen runtime import
graph. The final artifact remains the source of truth for what was distributed.

### PyInstaller

- Build package: `pyinstaller==6.21.0`
- Source: <https://github.com/pyinstaller/pyinstaller>
- License: GPL-2.0-or-later with the PyInstaller bootloader exception
- License text: `THIRD_PARTY_LICENSES/PyInstaller-6.21.0/COPYING.txt`

PyInstaller is used to build the application. Its bootloader exception permits
distribution of the resulting application under this project's GPL-3.0-only
license.

### Cython and setuptools

- Build package: `cython==3.2.8`
- Source: <https://github.com/cython/cython>
- License: Apache-2.0
- Build package: `setuptools==80.9.0`
- Source: <https://github.com/pypa/setuptools>
- License: MIT

Cython and setuptools are build-time tools used to compile the selected RC003
permission modules. They are not bundled as runtime packages in the Windows
application; the generated extension modules remain part of this project's
GPL-3.0-only corresponding source and binary distribution.

## Upstream protocol and implementation sources

### open-voice-bridge Windows implementation

- Project: `nijez/open-voice-bridge`
- Source: <https://github.com/nijez/open-voice-bridge>
- License: GNU General Public License v3.0 only (`GPL-3.0-only`)

The Windows RC003 implementation in `apps/windows/rc003` is adapted from the
upstream Windows client. Attribution and local changes are summarized in
`apps/windows/rc003/ATTRIBUTION.md`.

### remote-bridge-hub

- Project: `xxb26553663-star/remote-bridge-hub`
- Source: <https://github.com/xxb26553663-star/remote-bridge-hub>
- Reference revision: `8a93f321ac71a602300c6cd77f7256fa4b63068e`
- License: GNU General Public License v3.0 only (`GPL-3.0-only`)

The Xiaomi RC003 ATVV UUIDs, microphone command behavior, IMA/DVI ADPCM
decoding order, capability parsing and HID usage mapping are protocol
references for this Windows client. No upstream customer data or commercial
branding is included.

## Separately licensed assets and software

### Chromecast product photo

`Resources/Chromecast-remote-photo.png` is the user-supplied photo selected on
2026-09-16 for the Chromecast mapping page. It was imported without changing
pixels. The copyright owner confirmed on 2026-09-24 that this unchanged image
may be publicly redistributed with Remote Mic. See `ASSET_LICENSES.md` for the
permission boundary; this notice does not grant broader reuse or modification.

### RC003 product photo

The bundled file `Resources/RC003-remote-photo.png` was independently created
by the repository maintainer from a personally owned RC003 product. It is
licensed under GPL-3.0-only with the rest of this repository. Product names,
appearance and visible third-party marks remain the property of their
respective owners and are shown only to identify compatible hardware.

### VB-CABLE

- Project: VB-Audio VB-CABLE
- Source and donation page: <https://vb-audio.com/Cable/>
- Package: `VBCABLE_Driver_Pack45.zip`
- License: VB-Audio Donationware / vendor terms; not GPL code

The `fetch-vb-cable.ps1` build helper downloads the official unmodified Basic
package and verifies its pinned SHA-256. The bundle never includes the paid
A+B/C+D products. The client does not re-license or silently install VB-CABLE,
and it never changes the Windows system default input/output device; audio is
written only to an explicitly selected endpoint. Installation starts only after
an explicit user action and Windows UAC confirmation. The installation action
does not elevate the main process itself; users may have started the application
as administrator under the current public-version workaround. It never reports a driver install as
successful merely because a process was launched. Users may obtain the same
package directly from VB-Audio and are encouraged to support the vendor through
its Donationware model.

## Microsoft runtime components

The frozen Windows application may include Microsoft Universal C Runtime and
Visual C++ runtime DLLs redistributed under Microsoft's applicable runtime
terms. They are not part of this project's GPL source code.

## Fun-ASR-Nano CPU runtime（RC003 1.0.105 local test）

Fun-ASR-Nano model/GGUF artifacts and the Fun-ASR CPU runtime originate from [QwenAudio/Fun-ASR](https://github.com/QwenAudio/Fun-ASR) / [FunAudioLLM/Fun-ASR-Nano-GGUF](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-GGUF), licensed under Apache-2.0. llama.cpp/ggml are under MIT. The native test runtime adapts the upstream CLI to a bounded anonymous-pipe protocol with in-memory audio, persistent model reuse and configurable CPU threads. Source revision, patches, build recipe and third-party notices are in `apps/windows/rc003/build/nano/`; the corresponding source archive includes exact upstream source archives. MinGW compiler runtime use is subject to its notices and applicable GCC Runtime Library Exception. No upstream endorsements are implied.

Model weights are separately downloaded and SHA-256 verified. They are not bundled in the portable ZIP. Hotword editing is not implemented in this local test build. Whisper/Paraformer retain their original notices and behavior.

## Qwen3-ASR-0.6B 源码测试依赖（RC003 1.0.106）

Qwen3-ASR模型与Transformers实现见 https://huggingface.co/Qwen/Qwen3-ASR-0.6B-hf 和 https://github.com/huggingface/transformers ，按各自Apache-2.0许可使用。模型固定revision和各文件校验标识保存在`model_downloads.py`。新版Transformers/Hub/tokenizers/safetensors及其依赖仅安装到独立源码测试目录，未替换既有引擎依赖。该目录内各发行包的dist-info中保留原有LICENSE/NOTICE；本轮不制作或交付新的应用包。CPU推理复用已有CPU版PyTorch，其既有许可通知继续适用。
