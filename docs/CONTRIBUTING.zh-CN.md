# 贡献指南

感谢你帮助改进录制后的素材整理体验。

## 本地开发

安装 Python 3.11+ 和 FFmpeg，然后执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
pytest -q
python -m build
```

## 提交 Pull Request

- 保持文件操作保守：禁止静默覆盖、未确认改名或未审核归档。
- 把视觉相似度视为启发式结果，文件移动前必须保留审核步骤。
- 每项行为变更都应增加测试，尤其是错误路径和回滚逻辑。
- 保持 JSON 输出兼容；如果有意调整 schema，请同时更新版本和文档。
- 未经明确的 opt-in 设计，不要增加云端依赖或收集媒体数据。
- 不要把私人录像、截图、绝对路径或未脱敏元数据提交到 Issue、测试和文档。

## 提交前检查

```bash
ruff check .
pytest -q
python -m build
video-intake doctor
```

## Issue

提交 Bug 时请包含：使用的命令、脱敏后的 JSON 输出、操作系统、Python 版本和 FFmpeg 版本。尽可能提供最小化的可公开复现素材，不要把私人视频上传到公开 Issue。

安全漏洞请按照 [SECURITY.md](../SECURITY.md) 私下报告。
