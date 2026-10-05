# ASD-STE100 中文版 —— 面向代理输出的简化技术中文

一个 Claude Code 技能，把密集、含糊的中文改写或展开为可无歧义解析的形式。它适用于 [ASD-STE100 简化技术英语](https://www.asd-ste100.org/)原则的中文移植。

本技能服务于需要准确理解文本的机器、下游代理、视觉模型和制作人员。除代理输出、工具描述、报错信息和代理间指令外，它也能处理场景说明、空间布局、物体位置、遮挡、包含关系、镜头和分镜约束。

它不负责替用户创作故事、风格、审美或情节。创作说明中的结构化语义可以处理：例如把“箱子在灯旁边”改成带明确参照物的空间关系。必要时可以做最小语义展开，但不凭常识补充原文没有的方向、位置、因果或时间。

这是 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill) 的中文适配版。不是翻译：中文没有时态变位、冠词和短语动词，但有自己独有的歧义源。规则做了对应替换，linter 从零重写，检查中文的结构违规。

## 为什么 STE,为什么用于代理

STE 的存在是因为飞机上一条误读的指令会死人,而读者常是非英语母语者,没有作者可追问。标准的解法:一词一义、主动语态、简单时态、一句一指令、短句、不省略成分。

解析另一个代理输出的 LLM 处境惊人地相似——没有回传信道,没法问"你是指 X 还是 Y?"。让机械师不误读扭矩规格的规则,同样让下游代理不误读工具描述或代理间消息。

## 中文适配了什么

| 英文 STE 规则 | 中文对应 |
|---|---|
| 禁现在完成时等复合时态 | 完成标记不叠加("已经完成了" → "已完成");"可能已失败"这类情态+完成受保护 |
| 冠词、主语不省略 | 主语不省略——流水句共享主语,代理无法确定小句主语是否延续 |
| 句长 ≤20/25 词 | ≤25 字(指令)/ ≤40 字(描述) |
| 名词堆叠 ≤3 词 | 前置定语 ≤3 层,更长则后置或拆句 |
| 禁短语动词(take off、spin up) | 禁黑话动词(拉起、落地、打通、赋能) |
| 禁分号(规则 8.1) | 原样保留,中英文分号皆禁 |
| 一词一义(官方词典) | 中文无官方受控词典,文档内一致性仍机械可查,词典合规降为建议 |
| (新增) | 流水句拆分:逗号不连接两个独立指令 |

## 改写前 / 改写后

| 改写前 | 改写后 |
|---|---|
| "本工具将尝试在已被配置的各个后端之间同步状态,若检测到冲突,则可能会依据当前所设置的策略自动加以解决,否则会将该冲突呈报以供人工审查。" | "本工具尝试同步各后端之间的状态。各后端均已配置。若发现冲突,工具读取已配置的策略。若策略允许自动解决,工具可以不经用户解决冲突。若工具未解决冲突,则呈报该冲突,供人工审查。" |
| "处理您的请求时可能发生了错误,原因或许是预期数据格式存在潜在不匹配,而这可能由过期的客户端版本所导致。" | "你的请求可能已失败。原因可能是数据格式与服务器期望的不匹配。过期的客户端会导致该不匹配。请检查客户端版本。" |

更多示例(含官方 STE 规则本身的图解)见 [`examples/before-after.md`](examples/before-after.md)。

## 本技能做什么

1. 识别文本作用：机器解析、制作执行、场景约束，或创作本体。
2. 选择操作：**改写**只改变措辞；**语义展开**把来源已有但未显式表达的实体、参照物、关系、条件、顺序和范围写出来。
3. 逐句检查含糊选词、完成标记叠加、无执行者的被动句、一句多指令、前置定语堆叠、成分省略、超长句、黑话动词、名词化动作、分号、hedging 堆叠、营销形容词和流水句。
4. 对空间或物体关系，明确参照系、实体身份、关系方向、关系类型和未指定项。只展开表达，不替用户完成构图。
5. 输出可直接使用的处理后文本。保留原文的事实、条件、范围限定词和 hedging，不新增来源没有的创意、位置、方向、因果、时间或审美选择。

要求看推理过程(“show the diff”或“解释改动”)则输出前后对照表。

结构性规则是机械的——能指出违反每条规则的确切字或标点。依赖 ASD 词典的规则标记为建议而非强制,需要品味的规则留给你。

linter 只检查结构模式。它不对比原文与改写、不验证要求强度未变、不证明改写保留了含义。零违规结果意味着配置的结构检查没有发现问题。

确定性 linter 检查:分号、黑话动词、名词化、营销形容词、被动语态、完成标记叠加、长句、同义轮换、受支持列表项中的悬挂连词。它从不标记 hedging 或情态。

悬挂连词规则检查行首 0–3 个前导空格加 ASCII 空格的列表标记。支持无序标记 `-`、`*`、`+`,以及以 `.` 或 `)` 结尾的有序数字标记(`1.`、`1)`)。它检查到最终有效行为止的缩进续行,不解析引用块、懒惰续行或完整嵌套列表语义。4 个及以上前导空格的独立行不视为列表标记。

刻意无效的 `examples/linter-edge-cases.md` 演示不完整的 Markdown 列表项。运行 `python3 scripts/ste-lint-zh.py examples/linter-edge-cases.md` 确认 linter 报出两处预期发现。该文件是测试夹具,不应作为合规 STE 散文使用。

本技能**不**复述 ASD 官方约 900 词批准词典。标准免费获取但不可自由再分发:第 9 期只允许经 ASD 书面授权或八类列出机构复制,本项目不在其列。本技能应用其*底层原则*(选最平实的词,每次用法一致)而非对照固定词表。需要认证 STE 合规文档时,请使用真正的标准。

完整规则摘要与引用:[`references/writing-rules.md`](references/writing-rules.md)。

## 安装

SKILL.md 遵循开放的 [Agent Skills 规范](https://agentskills.io/specification)(Anthropic 开源),格式本身跨工具通用;**装到哪取决于哪个 harness 来读它**。同一份技能目录,不同工具的发现路径:

| Harness | 用户级路径 | 项目级路径 |
|---|---|---|
| Claude Code | `~/.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` |
| Codex CLI | `~/.agents/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md`(从 CWD 向上扫到仓库根) |
| OpenCode | `~/.config/opencode/skills/`,另原生识别 `~/.agents/skills/` 与 `~/.claude/skills/` | `.opencode/skills/`,另识别 `.agents/skills/` 与 `.claude/skills/`(从 CWD 走到 git 根) |
| omp | `.agents/skills` 是规范位置;另识别 `~/.omp` 插件与 claude/codex/opencode 目录(用户级外部目录经 `enabledProviders` 启用) | 同左 |

多工具用户建议装 `~/.agents/skills/`——Codex 原生扫这里,OpenCode 原生识别,omp 视其为规范位置,再向 `~/.claude/skills/` 等做符号链接,一份文件服务全部。各路径都要求技能目录**恰好一层**位于 skills 根之下(`<skills-root>/asd-ste100-zh/SKILL.md`),不支持嵌套;OpenCode 还要求 frontmatter `name` 与目录名一致(本技能满足)。

### skills CLI(推荐,自动落位)

```bash
npx skills add archebase/asd-ste100-zh
```

[skills CLI](https://www.skills.sh/docs/cli) 支持包括 Claude Code、Codex、OpenCode 在内的 70+ 工具,会探测你用的 harness 并写入其约定路径。匿名遥测(技能名与时间戳,无个人信息)用于排行榜,`DISABLE_TELEMETRY=1` 可关。日后 `npx skills update` 更新。

### 手动安装

```bash
# 装到跨工具约定路径,然后按需软链到各 harness
git clone https://github.com/archebase/asd-ste100-zh ~/.agents/skills/asd-ste100-zh
ln -s ~/.agents/skills/asd-ste100-zh ~/.claude/skills/asd-ste100-zh   # 若还用 Claude Code
```

或直接把本目录(含 `SKILL.md`、`references/`、`examples/`、`scripts/`、`evals/`)复制到你所用 harness 的 skills 路径下。

### 设为所有工作区的默认(Codex)

用户级安装只保证 Codex 能发现本技能,不保证 Codex 调用它。要让它成为默认行为,再补两步。

**1. 显式启用。** 写进 `~/.codex/config.toml`,让技能出现在清单里,并阻止其他配置关掉它:

```toml
[[skills.config]]
path = "/Users/<you>/.agents/skills/asd-ste100-zh/SKILL.md"
enabled = true
```

**2. 全局指针。** 写进 `~/.codex/AGENTS.md`,让模型默认往这条路上走:

```md
## Chinese text defaults to the asd-ste100-zh skill

When I write Chinese text that another agent, tool, or pipeline must parse with
no human in the loop, default to the `asd-ste100-zh` skill instead of asking
first. Does not apply to creative writing, marketing copy, or anything where
tone and nuance are the point.
```

改完 `config.toml` 需要重启 Codex。仓库级 `AGENTS.md` 优先级高于全局,团队约定放仓库。

| 机制 | 保证 |
|---|---|
| 技能装在用户级路径 | 所有工作区都能发现 |
| `skills.config.enabled = true` | 技能出现在清单里,保持启用 |
| 全局或仓库 `AGENTS.md` | 模型默认执行,高概率但不机械 |
| `scripts/ste-lint-zh.py` 进 pre-commit 或 CI | 确定性 |

想要机械强制,门禁是 linter,不是技能本身。存量文档用 `--baseline N` 容忍既有违规,逐步收敛。

激活范围、优先级和不适用边界见 `SKILL.md` 的「默认激活与边界」一节。

## 用法

用简化或澄清中文文本的请求触发:

```
消除这段工具描述的歧义
改写这条报错,让代理不会误解析
对这段指令应用简化技术中文
把这段中文改写到机器能无歧义解析
```

或粘贴文本并要求"简化这段中文" / "消除歧义" / "把这段输出改得更明确"。

你会拿回改写后的文本,没有别的。要看应用了哪些规则,在请求中加"show the diff"或"解释改动"。

## 范围

适用于:代理间消息、工具/函数描述、报错信息、系统提示词、代理间指令——任何机器或非母语读者必须在无人可问的情况下解析的中文文本。

不适用于:创意写作、营销文案,或语气与微妙是重点的任何文本——STE 刻意平直、字面。

## 评测

三层评测见 [`evals/README.md`](evals/README.md):

1. **linter 召回/负例清洁**(离线,`evals/run_eval.py`):14 条标注违规正例 + 8 条合规负例,当前 14/14、8/8;
2. **金标改写属性**(同上):9 对前后改写,断言零硬违规、hedging 同族保留,当前 9/9;
3. **模型在环 benchmark**(`evals/run_bench.py`,需 eval kernel):SKILL.md 作 system prompt 改写语料,judge 评语义保持/情态保持/输出格式三维度,基线三项全过 2–3/9。

离线层已抓到并修复过一个真 bug(中文切句沿用英文"标点+空白"规则导致整段误判长句)。benchmark 稳定复现的模型缺陷模式:`保留原文:`膨胀成多行、压缩中丢限定词、发明原文没有的结构。

一个值得先说的局限:这修复文本的形式,不修复实质。没什么可说的段落改出来短、干净,但仍然空洞。

## 致谢与许可

基于 [danyuchn/asd-ste100-skill](https://github.com/danyuchn/asd-ste100-skill)(MIT)适配。MIT —— 见 [LICENSE](LICENSE)。
