# 发布 1.0.107 到 GitHub

目标仓库：https://github.com/WuYuStar/vibenano

1. 把本次源码改动提交并推送到目标仓库，保留 LICENSE、COPYRIGHT、ATTRIBUTION、第三方许可和构建资料。不要上传 `.build`、dist、虚拟环境、模型缓存、录音、日志、个人配置或凭据。
2. 对确认的提交创建 `v1.0.107` 标签。打开 Releases，创建该标签的预发布（Pre-release），标题“VibeNano 1.0.107（预发布）”。
3. 将 RELEASE_NOTES_1.0.107.md 的内容作为发布说明。
4. 附加准备目录中的 portable ZIP、source ZIP 和 SHA256SUMS.txt。source ZIP包含当前完整源码和Nano固定上游归档，请一起上传；不能只依赖GitHub自动生成的不含第三方归档的Source code附件。
5. 发布后检查附件能下载，摘要与 SHA256SUMS.txt 一致，再把首页“发布准备”改成实际发布链接。

源码附件由当前工作树导出，包含尚未提交的新文件；推送时也必须包含这些文件，保证仓库、标签和源码附件一致。不要从先前版本的 Git HEAD 导出后误标为1.0.107。

本次公开应用包移除了VB-CABLE安装文件，原有桌面自用包保持原样。外部输入法用户需自行下载安装驱动；Nano不需要该驱动。权限边界与依据见 THIRD_PARTY_NOTICES.md。

已检查：主项目GPL来源、既有素材授权记录、Qt对应源码记录、Nano源码归档、依赖许可和待上传清单。源码回归属于前一轮结果；本轮不重跑长时间测试，也未补做冻结应用运行测试。因此本版标为预发布。

维护者重新生成附件：`python apps/windows/rc003/build/prepare-public-release.py --portable 应用ZIP路径 --output 一个新的输出目录`。导出器校验Nano源码摘要、排除本机目录、检查常见凭据特征、移除随包驱动并生成校验清单；这不能替代人工检查或软件功能测试。
