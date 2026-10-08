# ASD-STE100 简化技术中文

把中文写成、改写成或展开成机器与下游读者可无歧义解析的形式：工具与函数描述、schema 字段说明、报错信息、系统提示词、代理间指令、状态报告，以及画面、场景、空间布局、物体关系、分镜、镜头和视觉生成提示词。本技能属于 ArcheBase 技能库中的中文表达层：它只负责表达形式——选词、句法、句子结构、关系显式化——不负责内容创作。`SKILL.md` 是代理行为契约，触发条件、模式、流程、输出格式与边界都写在那里；本 README 是仓库级导览，不单独承载任何代理规则。

| Field | Value |
|---|---|
| Skill id | `asd-ste100-zh` |
| Version | `0.3.0` |
| License | `Internal` |
| Status | 内部技能（frontmatter `license: Internal`），`SKILL.md` 版本 `0.3.0` |
| Repository | `https://github.com/archebase/asd-ste100-zh.git` |

## Scope
- **Owns:** 中文的受控表达——短句、单义、主动语态；流水句拆分；去名词化与黑话动词；一词一义的文档内一致性；空间、物体、场景、镜头关系的显式化（参照系、实体身份、方向、关系类型、未指定项）；在不新增事实的前提下做语义展开。
- **Delegates:** 无 —— `SKILL.md` 未定义对其他技能的路由。
- **Refuses:** 创作本体（故事、诗歌、广告、品牌口号、需要保留语气与隐喻的文案）；用户提供的原文与自己的对话回复（用户未要求改写时）；替用户决定未指定的左/右、前/后、内/外、远/近、遮挡、因果、时间或审美；复述 ASD 官方约 900 词批准词典；保证航空航天级 STE 合规文档；把空洞内容改得真实。

## Modes
| Mode | Use when | Required evidence |
|---|---|---|
| 严格 | 操作步骤、报错信息、工具与函数描述、代理间指令、安全文本，以及场景、空间、物体关系说明——误读有代价的场合 | 每条硬性违规可指名字或标点；结构性规则可先用 `scripts/ste-lint-zh.py` 机械初筛 |
| STE 风味 | README、PR 描述、变更日志、解释性散文 | 结构规则全部强制（句长上限、主动语态、拆流水句、禁分号、去名词化、去营销形容词），词汇规则降为建议 |

模式选择在改写前完成；用户未指定时由文本作用推断，并在一行内说明。模式（规则强度）与操作（改写 / 语义展开）是相互独立的两个选择。

## Quick start
1. 安装到用户级技能路径（见 Install）。
2. 直接起草约束性中文——工具描述、报错字符串、代理间指令、场景与镜头说明。用户级启用后本技能默认激活，不必等用户点名；判据是文本在规定如何理解、摆放、执行或核对，而不是文本属于哪个体裁。
3. 对已有文本，点名「消除歧义」「简化中文」「STE 中文改写」「受控中文改写」，或英文触发词 `disambiguate Chinese text`、`STE rewrite Chinese`、`expand spatial relations`、`write an unambiguous scene description`。
4. 默认只拿回处理后的文本。需要前后对照与逐条规则时，加「show the diff」或「解释改动」。
5. 需要本地初筛时：

```bash
echo "面板被移除;拉起任务。" | python3 scripts/ste-lint-zh.py
```

## Commands
| Command | Purpose |
|---|---|
| `python3 scripts/ste-lint-zh.py FILE` | 检查文件的结构违规；硬性违规超过基线（默认 0）时退出码 1 |
| `echo "文本" \| python3 scripts/ste-lint-zh.py` | 从 stdin 检查 |
| `python3 scripts/ste-lint-zh.py --json FILE` | 结构化 JSON 输出 |
| `python3 scripts/ste-lint-zh.py --baseline 5 FILE` | 允许最多 5 处硬性违规，用于存量文档逐步收敛 |
| `python3 scripts/ste-lint-zh.py --disable passive-voice,double-completion FILE` | 关闭指定规则 |
| `python3 scripts/ste-lint-zh.py --selftest` | 运行 linter 内置自检 |
| `python3 evals/run_eval.py` | 离线确定性评测：正例召回、负例清洁、金标改写属性、语义展开夹具 |
| `python3 evals/run_eval.py --json` | 同上，结构化输出 |

linter 检查分号、黑话动词、名词化、营销形容词、被动语态、完成标记叠加、长句、同义轮换和受支持列表项中的悬挂连词。它从不标记情态词（可能、或许、也许、大概）——置信度是内容，不是文体。

## Bundle layout
```text
SKILL.md      代理行为契约：触发、模式、流程、输出格式、边界
references/   writing-rules.md：ASD-STE100 第 9 期的规则章节与词典结构摘要，附引用
scripts/      ste-lint-zh.py：结构性规则的确定性 linter，仅用标准库
examples/     before-after.md；linter-edge-cases.md 是刻意违规的测试夹具
evals/        corpus.jsonl、run_eval.py、run_bench.py、bench-report.json、README.md
agents/       openai.yaml：宿主清单（display_name、默认提示词、允许隐式调用）
```
每个 reference 与脚本的加载触发条件写在 `SKILL.md` 的「附加资源」一节。

## Validation
```bash
python3 scripts/ste-lint-zh.py --selftest
python3 evals/run_eval.py
python3 scripts/ste-lint-zh.py examples/linter-edge-cases.md
```
`--selftest` 证明 linter 的内置断言通过；`run_eval.py` 证明 linter 在标注语料上的召回与负例清洁，并检查金标改写自身是否守规则（`evals/README.md` 记录 exit 0）。第三条是预期失败的夹具：它应报出 2 处 `dangling-conjunction` 并以退出码 1 结束，验证 linter 能报，不验证文本合规。三者都不证明含义保留：linter 只做结构模式检查，不对比原文与改写；「默认激活与边界」是提示词契约，不被本套评测覆盖。

## Install
```bash
git clone https://github.com/archebase/asd-ste100-zh.git
ln -s "$PWD/asd-ste100-zh" ~/.agents/skills/asd-ste100-zh
```
前置条件：只需 Python 3，`scripts/` 与 `evals/run_eval.py` 仅使用标准库；第 3 层 benchmark 另需 eval kernel 的 `completion`/`judge`。仓库无 git tag，安装即取 `main`。技能目录必须恰好一层位于 skills 根之下（`<skills-root>/asd-ste100-zh/SKILL.md`），不支持嵌套；多工具用户装 `~/.agents/skills/` 后再软链到 `~/.claude/skills/` 等 harness 路径。要让 Codex 默认调用它，还需在 `~/.codex/config.toml` 用 `[[skills.config]]` 写 `enabled = true`，并在 `~/.codex/AGENTS.md` 加默认指针——这是高概率而非机械保证；需要机械强制时，门禁是 `scripts/ste-lint-zh.py`，不是技能本身。

## Status
- 当前版本 `0.3.0`（`SKILL.md` frontmatter）。仓库无 `CHANGELOG.md`、无 git tag；`git log` 有三条提交：`04cf82b` 初始中文移植、`2b87977` 默认激活策略（SKILL.md 0.2.0）、`3b668d3` 语义展开边界澄清。
- 仓库内记录、非本次重跑：`evals/README.md` 记录离线层召回 14/14、负例清洁 8/8、金标属性 9/9、语义展开夹具 2/2、exit 0。
- 模型在环 benchmark 基线记录在 `evals/README.md` 与 `evals/bench-report.json`（2026-10，default 模型，glm-5.3 判分）：meaning 4/9、hedge 5/9、format 5/9，三项全过 3/9。重跑需在 eval kernel 内 `%load evals/run_bench.py`，且该脚本硬编码 `ROOT = /tmp/asd-ste100-zh`。
- 未运行 / 计划：本 README 不对改写质量做任何声明；「默认激活与边界」的激活策略不被现有评测覆盖，改动该节需人工跑负向用例。

## License and provenance
`LICENSE` 是 MIT 许可，版权声明两行：

```text
Copyright (c) 2026 Dustin Yuchen Teng
Copyright (c) 2026 asd-ste100-zh contributors (Chinese adaptation of asd-ste100-skill)
```

授权范围（`LICENSE` 原文）：

```text
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

`LICENSE` 中没有非商业、share-alike 或额外再分发限制条款；软件按 "AS IS" 提供，无任何明示或默示担保。

- 上游：本技能是 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill) 的中文适配版（MIT）。
- 标准来源：ASD-STE100 第 9 期（2025 年 1 月），<https://www.asd-ste100.org/>。`SKILL.md` 记录：第 9 期第 2 页声明未经 ASD 官员书面授权不得全部或部分复制或出版，只对八类列出机构授予免费复制权；本项目不在其列，因此约 900 词批准词典不进入本仓库。
- `SKILL.md` frontmatter 写 `license: Internal`，与 `LICENSE` 的 MIT 不一致；此表与本节按原文并列，不作统一。
