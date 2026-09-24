# WeChat Local Chat Analysis

[中文说明](#中文说明)

A privacy-first Codex Skill and Windows CLI for turning authorized screenshots from the official WeChat desktop client into reviewable OCR evidence, normalized JSONL, a correction queue, and a local report.

This project is designed for evidence-bounded analysis, not bulk account extraction. It does not decrypt WeChat databases, inject into processes, use unofficial clients or protocols, or upload chat data by default.

The CLI keeps its file pipeline on the local machine. Reading normalized chat text into Codex or another model is a separate processing boundary and requires an explicit preview and approval unless that model is verified as device-local.

## What it provides

- A reusable `$wechat-local-chat-analysis` Skill with explicit authorization and privacy gates.
- A capture-first workflow: finish and verify the approved screenshot range before OCR.
- A local CLI: `doctor`, `init-batch`, `capture`, `ocr`, `normalize`, `report`, and `prepare-online-review`.
- Schema-v1 manifests with workspace-relative paths, per-stage SHA-256 corruption checks, completed-capture registration, foreground process binding, and requested/actual OCR device records.
- Raw OCR preservation, normalized JSONL, low-confidence review CSV, and evidence-aware local reports.
- Strict identifier, date, path-containment, symlink, and spreadsheet-formula protections.

## Boundaries

- Supported: Windows 10/11, Python 3.11-3.12, and the official WeChat desktop client.
- CPU is the compatibility baseline. PaddleOCR 3.x is optional; users choose and install the appropriate PaddlePaddle CPU or GPU framework.
- The CLI does not grant permission to access a conversation. Use it only for content you are authorized to view and analyze.
- `prepare-online-review` creates a local candidate bundle only. It never uploads data or calls a hosted model.
- Real chats, contacts, screenshots, OCR results, reports, models, credentials, virtual environments, and local workspaces are not included in this repository.

## Install

Clone or download this repository into a folder named `wechat-local-chat-analysis`. To make it directly discoverable as a personal Codex Skill, place that folder under `%USERPROFILE%\.agents\skills\`, or ask `$skill-installer` to install it from the GitHub repository after publication.

Create an isolated Python environment from the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

Install the optional visible-screen capture integration only when that local UI workflow is required:

```powershell
python -m pip install -e ".[capture]"
```

For OCR, first choose and install the matching PaddlePaddle framework from the [official PaddleOCR installation guide](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/installation.html), then install the optional integration:

```powershell
python -m pip install -e ".[ocr]"
```

The first PaddleOCR run may download models. Review the download, network, storage, and license implications before proceeding.

## Quick start

The default runtime workspace is `%LOCALAPPDATA%\WechatLocalChatAnalysis`; use global `--workspace` to choose another local directory. Runtime data should not be stored in the Skill source tree.

```powershell
wechat-local-chat-analysis doctor
wechat-local-chat-analysis --help
wechat-local-chat-analysis init-batch --help
```

The module entry point is equivalent:

```powershell
python -m wechat_analyse --help
```

Recommended sequence:

1. Confirm the authorized contact, inclusive ISO date range, analysis question, and exclusions.
2. Run `doctor` and `init-batch`.
3. Before `capture`, verify the official WeChat conversation and choose a rectangle containing only the chat pane. The command binds to the approved foreground WeChat process, screenshots that region, and scrolls it; it interrupts if the foreground identity changes. Close unrelated windows and be ready to stop.
4. Complete and verify every registered screenshot, the date boundaries, continuity, and absence of unrelated content; only then run `ocr --acknowledge-capture-coverage`.
5. Run `normalize`, use the review CSV as a checklist for consequential or low-confidence items, and record verified corrections in the analysis notes; the CSV is not automatically imported back into JSONL. Then run `report` for the raw evidence index.
6. Read the normalized JSONL locally for the requested semantic summary; `report` is an evidence index, not a substitute for that analysis.
7. Keep the artifacts local. If external review is needed, use `prepare-online-review` to create a local candidate, redact it manually, inspect the exact result, and then obtain separate approval for any upload.

For the installed version's exact arguments, use `<command> --help`. Detailed operating guidance is in [the local pipeline reference](references/local-pipeline.md).

## Evidence and privacy model

- Identical screenshot hashes may be deduplicated. Identical text from different screenshots, times, or sources is preserved.
- Uncertain scrolling overlap is queued for review rather than silently discarded.
- Raw OCR text remains unchanged in local OCR/JSONL artifacts. Review CSV cells with formula-like prefixes are escaped only in the export.
- Reports must disclose missing boundaries, unresolved OCR, and other evidence limits.
- No chat content, identity, screenshot, or conclusion should be placed in durable agent memory.

See [capture guidance](references/capture-workflow.md), [the data contract](references/data-contract.md), and [the external review gate](references/external-review.md).

## Development and verification

The test suite uses synthetic fixtures only and must not open or operate WeChat, download OCR models, or copy local conversation data.

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -v
wechat-local-chat-analysis --help
wechat-local-chat-analysis doctor
```

CI is intended to use standard Windows GitHub-hosted runners with read-only repository permissions, no secrets, no caches, and no uploaded artifacts. GitHub currently documents standard hosted runner use as free for public repositories; larger runners and storage have different billing rules. Review the current [GitHub Actions billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) before enabling a materially different workflow. The workflow follows GitHub's [secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use), including pinning Actions to full commit SHAs.

## Skill format and project status

The repository follows the official [OpenAI Build skills guidance](https://developers.openai.com/codex/build-skills): a concise `SKILL.md`, UI metadata in `agents/openai.yaml`, and progressively disclosed references.

Version `0.1.0` targets a local, reviewable Windows workflow. It is not a general WeChat backup tool, an account recovery tool, or a substitute for legal or compliance review.

## Security and license

Read [SECURITY.md](SECURITY.md) before handling sensitive data. Third-party attribution is listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The project is released under the [MIT License](LICENSE). WeChat is a third-party product and trademark; this independent project is not affiliated with or endorsed by its owner.

---

## 中文说明

这是一个本地优先的 Codex Skill 与 Windows CLI：将用户有权查看和分析的官方 PC 微信聊天截图，整理为可复核的 OCR 证据、规范化 JSONL、人工校对队列和本地报告。

本项目强调“有边界的证据分析”，不是批量账号提取工具。它不解密微信数据库、不注入进程、不使用非官方客户端或私有协议，也不会默认把聊天数据上传到云端。

CLI 的文件流水线在本机运行；将规范化聊天文本交给 Codex 或其他模型属于另一条处理边界。除非已确认模型在设备本地运行，否则必须先预览精确批次并取得明确批准。

### 提供的能力

- 可复用的 `$wechat-local-chat-analysis` Skill，内置授权范围与隐私确认门。
- 先采集后处理：完成并核验已授权截图范围后，才进行 OCR。
- 本地 CLI：`doctor`、`init-batch`、`capture`、`ocr`、`normalize`、`report`、`prepare-online-review`。
- schema v1 manifest：保存工作区相对路径、分阶段 SHA-256 完整性检查、已完成采集登记、前台进程绑定，以及请求设备和实际 OCR 设备证据。
- 保留原始 OCR，生成规范化 JSONL、低置信度复核 CSV 和基于证据的本地报告。
- 对标识符、严格 ISO 日期、路径越界、符号链接和表格公式注入进行防护。

### 使用边界

- 首发支持 Windows 10/11、Python 3.11-3.12 和官方 PC 微信。
- CPU 是兼容基线。PaddleOCR 3.x 为可选能力，用户需自行选择并安装匹配的 PaddlePaddle CPU 或 GPU 框架。
- CLI 不等于访问授权；只能处理用户有权查看和分析的内容。
- `prepare-online-review` 只生成本地候选材料，不上传、不发送，也不调用在线模型。
- 仓库不包含真实聊天、联系人、截图、OCR 结果、报告、模型、凭据、虚拟环境或本地工作区。

### 安装

将本仓库克隆或下载到名为 `wechat-local-chat-analysis` 的目录。若希望 Codex 将其识别为个人 Skill，可把该目录放到 `%USERPROFILE%\.agents\skills\` 下；仓库发布后也可让 `$skill-installer` 从 GitHub 安装。

在仓库根目录创建隔离环境：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

仅在需要本地可见屏幕采集时安装可选采集集成：

```powershell
python -m pip install -e ".[capture]"
```

如需 OCR，先按 [PaddleOCR 官方安装说明](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/installation.html)选择并安装匹配的 PaddlePaddle 框架，再安装可选集成：

```powershell
python -m pip install -e ".[ocr]"
```

PaddleOCR 首次运行可能下载模型。继续前应确认网络访问、磁盘占用和许可证影响。

### 快速开始

默认运行工作区为 `%LOCALAPPDATA%\WechatLocalChatAnalysis`，可通过全局 `--workspace` 指定其他本地目录。不要把真实运行数据放进 Skill 源码目录。

```powershell
wechat-local-chat-analysis doctor
wechat-local-chat-analysis --help
wechat-local-chat-analysis init-batch --help
python -m wechat_analyse --help
```

推荐顺序：

1. 确认有权处理的联系人范围、包含首尾的 ISO 日期、分析问题和排除项。
2. 运行 `doctor` 与 `init-batch`。
3. 运行 `capture` 前，确认官方微信中的正确会话，并选择只包含聊天区域的矩形。该命令会绑定已确认的前台微信进程、截图所选区域并滚动；前台窗口身份变化时会中断。请关闭无关窗口并随时准备停止。
4. 核验每张已登记截图、日期首尾、连续性和无关内容后，才运行 `ocr --acknowledge-capture-coverage`。
5. 运行 `normalize`，把复核 CSV 作为重要或低置信度项目的检查清单，并在分析笔记中记录核验后的修正；CSV 不会自动回写 JSONL。随后运行 `report` 生成原始证据索引。
6. 在本地读取规范化 JSONL 生成用户所需的语义总结；`report` 只是证据索引，不能代替语义分析。
7. 默认保持本地处理。如确需外部复核，先用 `prepare-online-review` 生成本地候选包，再手动脱敏并核对最终范围；任何上传仍需单独明确批准。

安装版本的精确参数以各命令的 `--help` 为准。更多说明见[本地流程](references/local-pipeline.md)、[采集规范](references/capture-workflow.md)、[数据契约](references/data-contract.md)和[外部复核确认门](references/external-review.md)。

### 证据与隐私原则

- 只把 SHA-256 完全相同的截图视为确定重复；不同截图、时间或来源中的相同文本必须保留。
- 滚动重叠无法确定时进入复核，不静默删除。
- 原始 OCR 与 JSONL 不因表格安全处理而改变；仅在导出复核 CSV 时转义公式型前缀。
- 报告必须披露缺失边界、未解决 OCR 和其他证据限制。
- 不把聊天文本、身份、截图或分析结论写入持久记忆。

### 开发、验证与费用边界

测试只能使用合成 fixture，不应打开或操作微信、下载 OCR 模型或复制本地聊天数据。

```powershell
python -m compileall -q src tests
python -m unittest discover -s tests -v
wechat-local-chat-analysis --help
wechat-local-chat-analysis doctor
```

CI 预期使用标准 Windows GitHub 托管 runner，只读仓库权限，不使用 secrets、缓存或上传产物。GitHub 当前说明：public 仓库使用标准托管 runner 免费；更大 runner 与存储规则不同。如工作流发生实质变化，应重新核对 [GitHub Actions 计费文档](https://docs.github.com/en/billing/concepts/product-billing/github-actions)。工作流还应遵循 GitHub 的[安全使用指南](https://docs.github.com/en/actions/reference/security/secure-use)，包括把 Action 固定到完整 commit SHA。

仓库遵循 OpenAI 官方的 [Build skills 指南](https://developers.openai.com/codex/build-skills)，使用精简 `SKILL.md`、`agents/openai.yaml` 和按需加载的参考文档。

`0.1.0` 面向本地、可复核的 Windows 流程，不是通用微信备份、账号恢复或法律合规替代方案。安全说明见 [SECURITY.md](SECURITY.md)，第三方归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。项目采用 [MIT License](LICENSE)。微信是第三方产品与商标；本项目为独立项目，与其权利方无隶属或背书关系。
