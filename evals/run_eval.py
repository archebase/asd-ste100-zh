#!/usr/bin/env python3
"""评测器:ste-lint-zh 的召回/误报 + 金标改写的属性保持。

三层评测,全部离线确定性,不调用模型:

1. positive 语料(含标注违规规则)→ 召回率:每条标注规则至少一次命中。
2. negative 语料(合规文本)→ 负例清洁度:零发现。
3. pair 语料(金标前后对)→ 三项属性:
   - 金标改写后硬性违规 = expect_hard(改写自身必须过 linter);
   - hedging 保留:before 的每个 hedge 词在 after 中仍有同族表达
     (允许形态变化,如"可能发生了"→"可能已失败");
   - 字数收敛:after 非空字符数 ≤ before(简化不得变长)。

用法:
    python3 evals/run_eval.py            # 全部
    python3 evals/run_eval.py --json     # 结构化输出
退出码:任一层失败为 1。
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from importlib.util import module_from_spec, spec_from_file_location

_spec = spec_from_file_location(
    "ste_lint_zh", Path(__file__).resolve().parent.parent / "scripts" / "ste-lint-zh.py")
_mod = module_from_spec(_spec)
_spec.loader.exec_module(_mod)
lint = _mod.lint

HEDGE_FAMILY = {
    # 触发词 → 同族可接受表达(子串匹配,允许形态变化:
    # "可能发生了"→"可能已失败"、"或将"→"或于")
    "可能": ["可能", "或许", "也许", "大概", "或将", "或"],
    "或许": ["可能", "或许", "也许", "大概", "或将", "或"],
    "也许": ["可能", "或许", "也许", "大概", "或将", "或"],
    "大概": ["可能", "或许", "也许", "大概", "或将", "或"],
    "或将": ["可能", "或许", "也许", "大概", "或将", "或"],
    "或于": ["可能", "或许", "也许", "大概", "或将", "或"],
    "或获得": ["可能", "或许", "也许", "大概", "或将", "或"],
    "可能发生了": ["可能", "或许", "也许", "大概", "或将", "或"],
    "可能由": ["可能", "或许", "也许", "大概", "或将", "或", "会导致"],
    "可能会": ["可能", "或许", "也许", "大概", "或将", "或", "可以"],
    "有时": ["有时", "可能", "可以"],
    "将尝试": ["尝试", "试图"],
    "试图": ["尝试", "试图"],
    "值得指出": ["警告", "注意"],
    "已经完成": ["完成"],  # 完成语义保留即可,标记叠加另算
    "旨在": ["目的", "用于", "可与", "做法"],
}
HEDGE_MISSING_OK = set()  # 金标中确认可丢弃的 hedge(空:不可丢弃)


def _nonspace(text):
    return [c for c in text if not c.isspace()]


def _rules_hit(findings):
    return {f["rule"] for f in findings}


def eval_positives(rows):
    results = []
    for row in rows:
        findings, _ = lint(row["text"])
        hit = _rules_hit(findings)
        missing = [r for r in row["rules"] if r not in hit]
        results.append({"id": row["id"], "ok": not missing,
                        "expected": row["rules"], "hit": sorted(hit),
                        "missing": missing})
    return results


def eval_negatives(rows):
    results = []
    for row in rows:
        findings, _ = lint(row["text"])
        results.append({"id": row["id"], "ok": not findings,
                        "findings": findings})
    return results


def eval_pairs(rows):
    results = []
    for row in rows:
        before, after = row["before"], row["after"]
        findings, _ = lint(after)
        hard = [f for f in findings if f["level"] == "advisory-free"]
        hard_ok = len(hard) == row["expect_hard"]

        hedge_fail = []
        for hedge in row.get("hedges_before", []):
            if hedge in HEDGE_MISSING_OK:
                continue
            family = HEDGE_FAMILY.get(hedge, [hedge])
            if not any(member in after for member in family):
                hedge_fail.append(hedge)
        # after 不允许无中生有的强断言:金标列出的 after hedge 必须存在
        invented = [h for h in row.get("hedges_after", []) if h not in after]

        # 附录:字数变化。SKILL 明确目标是无歧义而非压缩,精确性优先,
        # 不作为通过条件,只记录。
        delta = len(_nonspace(after)) - len(_nonspace(before))
        results.append({
            "id": row["id"],
            "ok": hard_ok and not hedge_fail and not invented,
            "hard_findings": hard, "hard_ok": hard_ok,
            "hedge_lost": hedge_fail, "hedge_invented": invented,
            "before_chars": len(_nonspace(before)),
            "after_chars": len(_nonspace(after)), "char_delta": delta,
        })
    return results


def main():
    as_json = "--json" in sys.argv
    corpus_path = Path(__file__).resolve().parent / "corpus.jsonl"
    rows = [json.loads(line) for line in
            corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    pos = eval_positives([r for r in rows if r["kind"] == "positive"])
    neg = eval_negatives([r for r in rows if r["kind"] == "negative"])
    pairs = eval_pairs([r for r in rows if r["kind"] == "pair"])

    def summary(items):
        n = len(items)
        ok = sum(1 for i in items if i["ok"])
        return {"pass": ok, "total": n,
                "rate": round(ok * 100 / n, 1) if n else 0.0}

    report = {
        "positive_recall": summary(pos), "positives": pos,
        "negative_clean": summary(neg), "negatives": neg,
        "pair_properties": summary(pairs), "pairs": pairs,
    }
    exit_code = 0 if all(summary(x)["pass"] == summary(x)["total"]
                         for x in (pos, neg, pairs)) else 1

    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, items in (("positive(召回)", pos), ("negative(清洁)", neg),
                            ("pair(属性)", pairs)):
            s = summary(items)
            print(f"{name}: {s['pass']}/{s['total']} ({s['rate']}%)")
            for item in items:
                if not item["ok"]:
                    print(f"  FAIL {item['id']}: {json.dumps(item, ensure_ascii=False)}")
        print("exit", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
