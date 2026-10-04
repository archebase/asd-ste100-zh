"""模型在环 benchmark:SKILL.md 作为 system prompt,改写 pair 语料的 before,
再用 judge 评三条属性。在 eval kernel 中运行(需要 completion/judge)。

评分维度(每条 0/1):
- meaning:改写后是否精确保留原文全部事实、条件与范围限定(无添加、无丢失)
- hedge:原文每个 hedging 的强度是否保留(可能→可能 可以;可能→断言 不行)
- format:输出是否只有改写文本(无前言/模式宣告/变更摘要/多余解释)

用法(kernel 内):
    %load evals/run_bench.py
"""
import json
from pathlib import Path

ROOT = Path("/tmp/asd-ste100-zh")
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
rows = [json.loads(l) for l in (ROOT / "evals" / "corpus.jsonl")
        .read_text(encoding="utf-8").splitlines() if l.strip()]
pairs = [r for r in rows if r["kind"] == "pair"]

async def run():
    sys_prompt = SKILL
    gens = {}
    for r in pairs:
        h = completion(f"对下面的文本应用本技能:\n\n{r['before']}", system=sys_prompt)
        gens[r["id"]] = h
    outs = {k: h.wait().strip() for k, h in gens.items()}
    questions = {
        "meaning": {"type": "bool", "instructions":
            "原句为机器解析而写。判断改写是否精确保留了原句的全部事实、条件、数字与范围限定:"
            "既没有丢失任何限定或条件,也没有添加原句未陈述的原因、频率或机制。轻微的措辞重组不算违规。"},
        "hedge": {"type": "bool", "instructions":
            "原句包含 hedging(可能/或许/或将/有时等不确定表述)。判断改写是否保留了这些不确定性的强度:"
            "hedging 可以换形态(如'可能发生了'→'可能已失败'),但不得升级为确定性断言,也不得新增断言。"
            "若原句没有 hedging,则判断改写是否未引入任何新的确定性因果宣称。"},
        "format": {"type": "bool", "instructions":
            "判断输出是否只包含改写后的中文文本本身:没有关于技能/模式的前言,没有违规计数,"
            "没有变更摘要或解释,没有结尾的补充说明。'保留原文:'单行说明是技能规范允许的唯一例外。"},
    }
    states = {r["id"]: {"before": r["before"], "rewrite": outs[r["id"]]}
              for r in pairs}
    b = judge_batch(states, questions, intent="STE-zh rewrite benchmark")
    results = {}
    async for k, item in b.drain_iter(timeout=600):
        results[k] = {"rewrite": outs[k], "answers": item.answers,
                      "error": item.error}
    per_q = {}
    for q in questions:
        ok = sum(1 for v in results.values() if v["answers"] and v["answers"].get(q, {}).get("bool", 0) >= 0.5)
        per_q[q] = {"pass": ok, "total": len(results)}
    overall = sum(1 for v in results.values()
                  if all(v["answers"].get(q, {}).get("bool", 0) >= 0.5 for q in questions))
    summary = {"per_question": per_q,
               "all_three": {"pass": overall, "total": len(results)}}
    out = {"summary": summary, "results": results}
    (ROOT / "evals" / "bench-report.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    display(json.dumps(summary, ensure_ascii=False))
    for k in sorted(results):
        v = results[k]
        flags = [q for q in questions if v["answers"].get(q, {}).get("bool", 0) < 0.5]
        if flags:
            display(f"FAIL {k}: {flags} -> {v['rewrite'][:80]}...")
    b.close()
    return summary
