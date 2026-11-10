# Fun-ASR-Nano Windows CPU runtime

Current source runtime, RC003 1.0.107. Model: FunAudioLLM/Fun-ASR-Nano-GGUF, f16 encoder + Q8_0 decoder and FSMN VAD. Three files total 1,275,804,800 bytes; downloaded separately. No GPU/PyTorch required by this engine. Nano is the only built-in local speech engine.

The persistent native worker accepts 16 kHz s16le PCM through anonymous pipes, emits length-prefixed UTF-8, and resets decoder context per segment. No recording files, network transcription or text logging. Native children inherit a kill-on-close Windows job from the isolated Python worker. Closing/switching engines reclaims their memory. Audio is processed after release. Silence is rejected by VAD; segments are joined with spaces. No editable hotword support. Store application launching is supported by the desktop application. Whisper conversion is no longer applicable because that engine was retired.

## Reproduce

Use exact source archives and checksums listed in native-build.json. Fun-ASR source commit prefix comes from GitHub's archive root; llama.cpp commit is pinned in that file. Extract archives to separate directories. In Fun-ASR runtime/llama.cpp, replace funasr-cli/funasr-cli.cpp with rc003-nano.cpp. Apply mingw-headers.patch to llama.cpp (only fills missing MinGW Windows SDK structure/constants for the existing thread throttling call).

Install MinGW-w64 POSIX GCC 13.2, CMake and Ninja. Configure the Fun-ASR runtime with:

```sh
cmake -S FUN_SOURCE/runtime/llama.cpp -B BUILD -G Ninja -DCMAKE_TOOLCHAIN_FILE=toolchain.cmake -DFETCHCONTENT_SOURCE_DIR_LLAMA=LLAMA_SOURCE -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON
cmake --build BUILD --target llama-funasr-cli -j 6
```

Copy BUILD/bin/llama-funasr-cli.exe to .build/nano-runtime/rc003-nano.exe before running source recognition or freezing; importing the source without recognition does not need this binary. This AVX2 build targets the user's i5-1340P and other CPUs with the listed instructions; older non-AVX2 PCs have not been validated. Static compiler runtime libraries use the GCC Runtime Library Exception; third-party licenses are supplied alongside this recipe and in the portable application's notices. Exact upstream source archives accompany the corresponding source distribution.


The reproducible helper is `python3 apps/windows/rc003/build/nano/build-runtime.py` on Linux/WSL (Python 3.12+, CMake, Ninja, patch and MinGW-w64 POSIX). It downloads only pinned archives, checks SHA-256, applies the supplied patch and builds the worker. To use the archives accompanying a release, pass `--archive-dir PATH`. Model weights are not part of this build.

Download requires a working verified HTTPS connection to GitHub. If local network/TLS policy prevents it, use the exact archives supplied in the release source ZIP with `--archive-dir`; never disable certificate validation. The new CI configuration has not yet been executed on GitHub.
