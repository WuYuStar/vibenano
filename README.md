# VibeNano

Windows 蓝牙遥控器语音输入与按键映射工具，支持小米遥控器2 Pro 和图示谷歌 Chromecast 遥控器。应用内名称暂沿用“无线麦”。

## 下载

[1.0.107 预发布](https://github.com/WuYuStar/vibenano/releases/tag/v1.0.107) · [版本说明](apps/windows/rc003/release-notes/1.0.107.md)

完整解压便携 ZIP，再运行其中的 `无线麦 win版 1.0.107.exe`。升级前请从托盘完全退出旧版；当前程序内更新入口沿用上游，升级本分支请从本仓库手动下载。

## 主要功能

- **本地语音识别**：Fun-ASR-Nano CPU 量化引擎，支持中英文混合输入；首次下载约1.28GB模型，之后可离线使用。
- **自定义按键**：单击、双击、长按分别映射快捷键、文字、Quicker 动作或打开程序，也可选择 ChatGPT 等商店应用。
- **录音反馈**：录音显示波形，识别显示圆环动画。
- **外部输入法**：保留搜狗、微信、豆包和 Chatterfly；使用这条路径需自行安装 VB-CABLE，本地识别不需要。

## 快速开始

1. 在 Windows 蓝牙设置中配对遥控器。
2. 打开程序，在“设备”页选择遥控器并启动服务。
3. 在“语音”页选择 Fun-ASR-Nano，下载模型。
4. 将光标放入文字框，按住话筒键说话，松开后输入文字。

按键映射在“按键”页修改；模型下载支持暂停、继续和失败重试。

要求 Windows x64，Nano 需要支持 AVX2/F16C/FMA 的 CPU，主要验证环境为 Windows 11。1.0.107 为预发布，打包后未补做运行测试，具体范围见版本说明。

[详细使用说明](apps/windows/rc003/README.md) · [源码构建](docs/BUILDING.md) · [问题反馈](https://github.com/WuYuStar/vibenano/issues)

## 来源与许可

由 [WuYuStar](https://github.com/WuYuStar) 基于 [ZSTDJan/windows-remote-mic-app](https://github.com/ZSTDJan/windows-remote-mic-app) 二次开发，Windows 实现源于 [nijez/open-voice-bridge](https://github.com/nijez/open-voice-bridge)。保留原作者版权与署名，按 [GPL-3.0-only](LICENSE.md) 发布。

[归属说明](apps/windows/rc003/ATTRIBUTION.md) · [第三方许可](legal/THIRD_PARTY_NOTICES.md) · [素材授权](legal/ASSET_LICENSES.md)
