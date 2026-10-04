#!/usr/bin/env python3
"""结构性 STE 规则的确定性 linter(中文版,ste-lint 的中文适配)。

只检查不需要 ASD 词典即可验证的规则。刻意从不标记情态词
(可能/或许/也许/大概):本技能把置信度视为内容,一个逼迫作者删掉
 hedging 的 linter 会改写论断本身。

与英文版的差异(不是翻译,是移植):
- 时态规则不存在中文形态对应物,改为"完成标记叠加"检查(已…了)。
- 短语动词规则对应中文黑话动词(拉起/落地/打通),降为建议级。
- 句长按字数(非空字符)计,上限 40 字;指令上限 25 字无法脱离上下文
  判断,与英文版一样只查描述性上限。
- 同义轮换组全部为技术文档中真正可互换的词;已排除"错误/故障"这类
  概念有别的近义词。

用法:
    ste-lint-zh.py FILE [FILE ...]
    echo "文本" | ste-lint-zh.py [--json]
    ste-lint-zh.py --baseline 5 FILE      # 硬性违规不超过 5 则通过
    ste-lint-zh.py --disable passive-voice,double-completion FILE
    ste-lint-zh.py --selftest

硬性(advisory-free)违规超过基线(默认 0)时退出码为 1。
建议级发现(被动语态、完成标记叠加、黑话动词)不会使运行失败。
"""
import json
import re
import sys

# 说明:全部是正则启发式,不是语法分析器。没有名词堆叠规则——那需要
# 词性标注才能避免持续误报;也没有省略成分规则:中文本来就不靠冠词,
# 该规则在中文里的形态("流水句省略主语")无法用正则可靠检出。
MARKETING_ADJ = r"(?:无缝|强大|业界领先|世界一流|革命性|颠覆性|极致|卓越|轻松|飞速|顶级|开创性|震撼|降本增效|一站式)"
SOFT_VERB = r"(?:拉起|落地|打通|闭环|抓手|赋能|串联|收口)"
VERBAL_NOUN = ("分析|检查|测试|优化|处理|评估|审查|调查|研究|比较|修改|更新|删除|"
               "验证|确认|解释|说明|讨论|部署|修复|备份|同步|迁移|重构|监控|记录|"
               "汇报|总结|审批|沟通|协调|梳理|排查|整改|迭代|交付")

RULES = [
    ("semicolon", "advisory-free",
     re.compile(r"[;；]"),
     "STE 禁用分号(规则 8.1)。拆成独立的句子。"),
    ("phrasal-verb", "advisory",
     re.compile(SOFT_VERB),
     "黑话动词。改用朴素的单词动词(启动、完成、整合、开始)。"),
    ("marketing-adjective", "advisory-free",
     re.compile(MARKETING_ADJ),
     "营销形容词。删除,或换成能支撑该说法的度量值。"),
    ("nominalization", "advisory-free",
     re.compile(r"(进行|开展|予以|实施)(了|一次|一项|一番|进一步|全面|深入|彻底)?(" + VERBAL_NOUN + ")"),
     "动作被包进名词。直接用动词(\"分析日志\",而非\"对日志进行分析\")。"),
    ("passive-voice", "advisory",
     re.compile(r"(?:被[一-龥]|受到|遭到|得以|为[一-龥]{1,8}所)"),
     "疑似被动语态。写明动作执行者并改用主动动词,除非执行者确实未知或不重要。"),
    ("double-completion", "advisory",
     # "可能已失败"这类情态+完成是受保护的 hedging,不是叠加
     re.compile(r"(?<!可能)(?<!或许)(?<!也许)(?<!大概)已[经]?[一-龥]{1,12}了"),
     "完成标记叠加(已…了)。保留其一即可,如\"已完成\"或\"完成了\"。"),
]

# 一词一义:同一动作常被轮换使用的动词组。只收真正可互换的词——
# "错误/故障/失败"是不同概念,不收。
SYNONYM_GROUPS = [
    ("检查", "核对", "校验", "查验"),
    ("删除", "移除", "清除"),
    ("停止", "终止"),
    ("显示", "展示"),
    ("使用", "利用", "运用"),
    ("发送", "传送"),
    ("获取", "取得"),
    ("修改", "变更", "改动"),
    ("创建", "新建", "建立"),
]

# 防误报:命中后面紧跟这些字时不算该词(显示器、检查点、利用率)。
_SUFFIX_BLOCK = {"检查": "点", "显示": "器", "修改": "器", "利用": "率"}

def _base_pattern(base):
    suffix = _SUFFIX_BLOCK.get(base)
    return re.compile(re.escape(base) + (r"(?![%s])" % suffix if suffix else ""))

MAX_CHARS = 40  # 描述性文本上限;指令上限 25 字无法脱离上下文判断

CODE_FENCE = re.compile(r"^(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
LIST_ITEM_START = re.compile(
    r"^(?P<indent> {0,3})(?P<marker>[-*+]|[0-9]+[.)])(?P<gap> +)(?P<body>.*)$"
)
CONJUNCTION_END = re.compile(r"(?:并且|或者|以及|还是|和|与|或|并|及|and|or)\s*$", re.I)
TABLE_SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")
SENTENCE_END = re.compile(r"(?<=[。!?!?])")

def _nonspace(text):
    return [c for c in text if not c.isspace()]

def _leading_spaces(line):
    return len(line) - len(line.lstrip(" "))

def _is_list_continuation(line, content_indent):
    if not line.strip():
        return True
    if LIST_ITEM_START.match(line):
        return False
    return _leading_spaces(line) >= content_indent

def _split_table_row(line):
    """Return trimmed table cells and their zero-based source columns.

    A pipe must separate at least two cells. Escaped pipes stay in their cell.
    This deliberately implements only the ordinary Markdown table shape; it is
    enough to distinguish a table from prose that happens to contain a pipe.
    """
    left = len(line) - len(line.lstrip())
    right = len(line.rstrip())
    content = line[left:right]
    if "|" not in content:
        return None
    if content.startswith("|"):
        content = content[1:]
        left += 1
    if content.endswith("|"):
        content = content[:-1]
    raw_cells = re.split(r"(?<!\\)\|", content)
    if len(raw_cells) < 2:
        return None

    cells = []
    column = left
    for raw_cell in raw_cells:
        leading = len(raw_cell) - len(raw_cell.lstrip())
        cells.append((raw_cell.strip(), column + leading))
        column += len(raw_cell) + 1
    return cells

def _markdown_table_cells(lines):
    """Map ordinary Markdown table rows to their prose cells.

    The separator row anchors detection, so pipe-containing prose is not
    treated as a table. Both leading-pipe and no-leading-pipe table styles are
    accepted when their header and body use the same number of cells.
    """
    table_cells = {}
    index = 1
    while index < len(lines):
        separator = _split_table_row(lines[index])
        header = _split_table_row(lines[index - 1])
        if (not separator or not header or len(separator) != len(header)
                or not all(TABLE_SEPARATOR_CELL.fullmatch(cell)
                           for cell, _ in separator)):
            index += 1
            continue

        table_cells[index - 1] = header
        table_cells[index] = []
        index += 1
        while index < len(lines):
            row = _split_table_row(lines[index])
            if not row or len(row) != len(separator):
                break
            table_cells[index] = row
            index += 1
    return table_cells

def _dangling_conjunction_findings(text, filename):
    lines = text.splitlines()
    findings = []
    in_fence = False
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if CODE_FENCE.match(stripped):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        start = LIST_ITEM_START.match(line)
        if not start:
            index += 1
            continue

        content_indent = (len(start.group("indent"))
                          + len(start.group("marker"))
                          + len(start.group("gap")))
        item_lines = [(index, start.group("body"))]
        next_index = index + 1
        item_fence = False
        while next_index < len(lines):
            candidate = lines[next_index]
            candidate_stripped = candidate.strip()
            if CODE_FENCE.match(candidate_stripped):
                # Fence delimiters are state markers, not meaningful item lines.
                item_fence = not item_fence
                next_index += 1
                continue
            if item_fence:
                next_index += 1
                continue
            if not _is_list_continuation(candidate, content_indent):
                break
            item_lines.append((next_index, candidate))
            next_index += 1

        meaningful = []
        for line_index, item_line in item_lines:
            # Preserve code spans as neutral operands while ignoring their contents.
            cleaned = INLINE_CODE.sub(" CODE ", item_line).strip()
            if cleaned:
                meaningful.append((line_index, cleaned))
        if meaningful:
            end_line_index, end_line = meaningful[-1]
            conjunction = CONJUNCTION_END.search(end_line)
        else:
            end_line_index, end_line, conjunction = None, None, None
        if conjunction:
            if end_line_index == index:
                finding_line = index + 1
                finding_col = start.start("marker") + 1
            else:
                raw_end_line = next(
                    raw for line_index, raw in item_lines
                    if line_index == end_line_index
                )
                masked_end_line = INLINE_CODE.sub(
                    lambda match: " " * len(match.group(0)), raw_end_line
                )
                raw_conjunction = CONJUNCTION_END.search(masked_end_line)
                finding_line = end_line_index + 1
                finding_col = raw_conjunction.start() + 1 if raw_conjunction else 1
            findings.append({
                "file": filename,
                "line": finding_line,
                "col": finding_col,
                "rule": "dangling-conjunction",
                "level": "advisory-free",
                "match": end_line,
                "message": "列表项以连接词结尾。补全该项,或与下一项合并。",
            })
        index = next_index
    return findings

def lint(text, filename="<stdin>"):
    findings = []
    chars_total = 0
    in_fence = False
    lines = text.splitlines()
    table_cells = _markdown_table_cells(lines)
    # first occurrence of each synonym-group member: (group_idx, base) -> (line, col, match)
    seen_synonyms = {}
    base_patterns = {base: _base_pattern(base)
                     for group in SYNONYM_GROUPS for base in group}
    for lineno, raw_line in enumerate(lines, 1):
        if CODE_FENCE.match(raw_line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        segments = table_cells.get(lineno - 1, [(raw_line, 0)])
        for segment, source_column in segments:
            line = INLINE_CODE.sub("", segment)
            chars_total += len(_nonspace(line))
            for rule_id, level, pattern, msg in RULES:
                for m in pattern.finditer(line):
                    findings.append({"file": filename, "line": lineno,
                                     "col": source_column + m.start() + 1,
                                     "rule": rule_id, "level": level,
                                     "match": m.group(0), "message": msg})
            for gi, group in enumerate(SYNONYM_GROUPS):
                for base in group:
                    if (gi, base) in seen_synonyms:
                        continue
                    m = base_patterns[base].search(line)
                    if m:
                        seen_synonyms[(gi, base)] = (
                            lineno, source_column + m.start() + 1, m.group(0)
                        )
            for sent in SENTENCE_END.split(line):
                n = len(_nonspace(sent))
                if n > MAX_CHARS:
                    findings.append({"file": filename, "line": lineno,
                                     "col": source_column + 1,
                                     "rule": "long-sentence", "level": "advisory-free",
                                     "match": f"{n} 字",
                                     "message": f"句子 {n} 字(上限 {MAX_CHARS})。拆分它。"})
    # synonym rotation: flag each member after the first, at its first occurrence
    for gi, group in enumerate(SYNONYM_GROUPS):
        present = [(seen_synonyms[(gi, b)], b) for b in group if (gi, b) in seen_synonyms]
        if len(present) > 1:
            present.sort()  # document order
            first_base = present[0][1]
            for (lineno, col, match), base in present[1:]:
                findings.append({"file": filename, "line": lineno, "col": col,
                                 "rule": "synonym-rotation", "level": "advisory-free",
                                 "match": match,
                                 "message": f"\"{base}\"和\"{first_base}\"指同一动作。选一个并始终使用。"})
    findings.extend(_dangling_conjunction_findings(text, filename))
    findings.sort(key=lambda f: (f["line"], f["col"]))
    return findings, chars_total

def report(findings, chars_total, as_json, hard_count, baseline):
    rate = round(len(findings) * 100 / chars_total, 1) if chars_total else 0.0
    if as_json:
        print(json.dumps({"violations": findings, "count": len(findings),
                          "hard_count": hard_count, "baseline": baseline,
                          "chars": chars_total, "per_100_chars": rate}, indent=2, ensure_ascii=False))
        return
    for f in findings:
        print(f"{f['file']}:{f['line']}:{f['col']} {f['rule']}: {f['message']} [{f['match']}]")
    print(f"\n{len(findings)} 处发现(硬性 {hard_count},基线 {baseline}),"
          f"{chars_total} 字,每百字 {rate} 处")
    print("情态词(可能、或许、也许、大概)永不被标记:置信度是内容。")

def selftest():
    bad = ("面板被移除;拉起任务。"
           "对日志进行一次分析。"
           "无缝的体验。"
           "已经收到了报告。")
    findings, _ = lint(bad)
    rules = {f["rule"] for f in findings}
    for expected in ("semicolon", "phrasal-verb", "nominalization",
                     "marketing-adjective", "passive-voice", "double-completion"):
        assert expected in rules, expected
    # hedges must never be flagged, including modality + completion
    findings, _ = lint("请求可能已失败。原因可能是超时。磁盘可能已写满。")
    assert findings == [], findings
    # code blocks skipped
    findings, _ = lint("```\nx = a; y = b\n```")
    assert findings == []
    # all supported list markers, case variants, and trailing whitespace
    findings, _ = lint(
        "- 确认目标,并\n"
        "* 记录结果,或者  \n"
        "+ 关闭面板\n"
        "1. 启动任务,并\n"
        "2) 停止任务或"
    )
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert len(dangling) == 4, dangling
    assert [f["line"] for f in dangling] == [1, 2, 4, 5], dangling
    assert [f["col"] for f in dangling] == [1, 1, 1, 1], dangling
    assert all(f["level"] == "advisory-free" for f in dangling), dangling

    # valid continuation lines and standalone four-space code are ignored
    findings, _ = lint("  - 确认目标,并\n    记录结果。")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 确认目标\n  并")
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert len(dangling) == 1 and dangling[0]["line"] == 2, dangling
    assert dangling[0]["col"] == 3, dangling
    findings, _ = lint("    - 代码,并")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("> - 确认目标,并\n> - 记录结果或")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 做这件事,并\n~~~\n代码,并\n~~~")
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert len(dangling) == 1 and dangling[0]["line"] == 1, dangling
    findings, _ = lint("```text\n- 代码,并\n```")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)

    # one- and three-space markers and ordered continuation width
    findings, _ = lint(" - 启动任务,并\n   记录结果。")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("-  启动任务,并\n   记录结果。")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("-\t启动任务,并")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("   - 启动任务,并", filename="fixture.md")
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert len(dangling) == 1 and dangling[0]["col"] == 4, dangling
    assert dangling[0]["file"] == "fixture.md"
    assert dangling[0]["match"].endswith("并")
    assert "补全该项" in dangling[0]["message"]
    findings, _ = lint("100. 启动任务,并\n  无关文本")
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert len(dangling) == 1, dangling
    findings, _ = lint("- 启动任务,并。\n- 停止任务或,")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 启动任务,并\n\n  记录结果。")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 父项,并\n  - 子项或")
    dangling = [f for f in findings if f["rule"] == "dangling-conjunction"]
    assert [f["line"] for f in dangling] == [1, 2], dangling

    # ordinary prose, inline code, and fenced code are ignored
    findings, _ = lint("该过程可能包含步骤,并")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 使用 `并` 作为标签")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("- 合并 `左` 和 `右`")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings), findings
    findings, _ = lint("~~~\n- 代码,并\n~~~")
    assert not any(f["rule"] == "dangling-conjunction" for f in findings)
    findings, _ = lint("字" * 40 + "。")
    assert any(f["rule"] == "long-sentence" for f in findings)
    findings, _ = lint("字" * 39 + "。")
    assert not any(f["rule"] == "long-sentence" for f in findings)
    # Markdown table syntax is layout, not prose. Each cell stays lintable.
    short_cell = " ".join(f"词{number}" for number in range(1, 9)) + "。"
    for table in (
            "| 标签 | 详情 |\n"
            "| --- | --- |\n"
            f"| 清晰 | {short_cell} |",
            "标签 | 详情\n"
            "--- | ---\n"
            f"清晰 | {short_cell}"):
        findings, chars_total = lint(table)
        assert not any(f["rule"] == "long-sentence" for f in findings), findings
        # header cells (4) + 清晰 (2) + cell terms + 。; separator row is empty
        expected = 6 + sum(len(f"词{n}") for n in range(1, 9)) + 1
        assert chars_total == expected, (chars_total, expected)
    long_cell = " ".join(f"词{number}" for number in range(1, 18)) + "。"
    findings, _ = lint(
        "| 标签 | 详情 |\n"
        "| --- | --- |\n"
        f"| 清晰 | {long_cell} |"
    )
    long_sentences = [f for f in findings if f["rule"] == "long-sentence"]
    assert len(long_sentences) == 1, long_sentences
    n_expected = sum(len(f"词{n}") for n in range(1, 18)) + 1  # + 句号
    assert long_sentences[0]["match"] == f"{n_expected} 字", long_sentences
    # synonym rotation: members after the first are flagged, first named as keeper
    findings, _ = lint("检查配置文件。然后核对输出。再校验一次。")
    rot = [f for f in findings if f["rule"] == "synonym-rotation"]
    assert len(rot) == 2, rot
    assert "\"核对\"和\"检查\"" in rot[0]["message"], rot
    # single consistent term: no flag
    findings, _ = lint("检查配置。检查输出。")
    assert not any(f["rule"] == "synonym-rotation" for f in findings)
    # suffix blocks: 显示器/检查点/利用率 are not rotation members
    findings, _ = lint("连接显示器。展示结果。")
    assert not any(f["rule"] == "synonym-rotation" for f in findings)
    findings, _ = lint("设置检查点。核对结果。")
    assert not any(f["rule"] == "synonym-rotation" for f in findings)
    # per-file labels
    findings, _ = lint("甲;乙", filename="x.md")
    assert findings[0]["file"] == "x.md"
    print("selftest OK")

def main(argv):
    if "--selftest" in argv:
        selftest()
        return 0
    as_json = "--json" in argv
    baseline = 0
    disabled = set()
    paths = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--baseline":
            i += 1
            baseline = int(argv[i])
        elif a == "--disable":
            i += 1
            disabled = set(argv[i].split(","))
        elif not a.startswith("--"):
            paths.append(a)
        i += 1

    findings, chars_total = [], 0
    if paths:
        for p in paths:
            f, w = lint(open(p, encoding="utf-8").read(), filename=p)
            findings.extend(f)
            chars_total += w
    else:
        findings, chars_total = lint(sys.stdin.read())

    findings = [f for f in findings if f["rule"] not in disabled]
    hard_count = sum(1 for f in findings if f["level"] == "advisory-free")
    report(findings, chars_total, as_json, hard_count, baseline)
    return 1 if hard_count > baseline else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
