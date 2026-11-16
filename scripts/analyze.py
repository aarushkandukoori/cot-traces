"""Count, grade and plot the captured traces, and write the site's data file.

Inputs  runs/*.jsonl (from gen.py) and scripts/grades_*.json (hand grades).
Outputs runs/stats.csv, runs/summary.json, figs/fig_tokens.pdf/.png,
        and <site>/data/traces.js when --site is given.
"""
import argparse
import csv
import json
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUNS = os.path.join(ROOT, "runs")
FIGS = os.path.join(ROOT, "figs")

MODELS = [
    # (key, file, grades file, label, mode)
    ("r1", "r1distill15_think.jsonl", "grades_r1.json", "DeepSeek-R1-Distill-Qwen-1.5B", "think"),
    ("q3", "qwen3_17_think.jsonl", "grades_q3.json", "Qwen3-1.7B", "think"),
    ("q3off", "qwen3_17_nothink.jsonl", "grades_q3off.json", "Qwen3-1.7B, thinking off", "nothink"),
]

# Words that mark a change of mind or a check. Counted in the thinking text only.
TURN_RE = re.compile(r"\b(wait|hmm+|hold on|actually|alternatively)\b", re.I)
WAIT_RE = re.compile(r"\bwait\b", re.I)
CHECK_RE = re.compile(r"\b(double[- ]check\w*|let me check|let me verify|verify|make sure|let me confirm)\b", re.I)


def load(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=None, help="site folder to write data/traces.js into")
    args = ap.parse_args()

    questions = json.load(open(os.path.join(HERE, "questions.json")))
    qorder = [q["id"] for q in questions]
    runs = []
    for key, fname, gname, label, mode in MODELS:
        rows = load(os.path.join(RUNS, fname))
        gpath = os.path.join(HERE, gname)
        grades = json.load(open(gpath)) if os.path.exists(gpath) else {}
        for r in rows:
            g = grades.get("%s|%d" % (r["qid"], r["seed"]))
            if rows and g is None:
                raise SystemExit("missing hand grade for %s %s seed %d" % (key, r["qid"], r["seed"]))
            t = r["thinking"]
            runs.append({
                "model": key, "label": label, "mode": mode, "qid": r["qid"], "seed": r["seed"],
                "n_thinking": r["n_thinking"], "n_answer": r["n_answer"],
                "finished": r["think_closed"] and r["finish_reason"] == "stop",
                "waits": len(WAIT_RE.findall(t)), "turns": len(TURN_RE.findall(t)),
                "checks": len(CHECK_RE.findall(t)),
                "correct": g["correct"], "final": g["final"], "think_end": g.get("think_end", ""),
                "mismatch": g.get("mismatch", False), "note": g.get("note", ""),
                "thinking": t, "answer": r["answer"].strip(),
                "temp": r["temp"], "top_p": r["top_p"], "top_k": r["top_k"],
                "max_tokens": r["max_tokens"], "tps": r["generation_tps"],
            })

    # per-run table
    os.makedirs(RUNS, exist_ok=True)
    cols = ["model", "mode", "qid", "seed", "n_thinking", "n_answer", "finished", "waits",
            "turns", "checks", "correct", "final", "think_end", "mismatch"]
    with open(os.path.join(RUNS, "stats.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in runs:
            w.writerow({c: r[c] for c in cols})

    # per question and model summary
    summary = {"by_question": {}, "by_model": {}}
    for key, _, _, label, mode in MODELS:
        mr = [r for r in runs if r["model"] == key]
        if not mr:
            continue
        summary["by_model"][key] = {
            "label": label, "runs": len(mr), "correct": sum(r["correct"] for r in mr),
            "median_thinking": statistics.median(r["n_thinking"] for r in mr),
            "max_thinking": max(r["n_thinking"] for r in mr),
            "unfinished": sum(not r["finished"] for r in mr),
            "runs_with_wait": sum(r["waits"] > 0 for r in mr),
            "total_waits": sum(r["waits"] for r in mr),
            "mismatch": sum(r["mismatch"] for r in mr),
        }
        for q in qorder:
            qr = [r for r in mr if r["qid"] == q]
            if not qr:
                continue
            summary["by_question"].setdefault(q, {})[key] = {
                "correct": sum(r["correct"] for r in qr), "runs": len(qr),
                "thinking": [r["n_thinking"] for r in qr],
                "median_thinking": statistics.median(r["n_thinking"] for r in qr),
                "waits": [r["waits"] for r in qr],
            }
    json.dump(summary, open(os.path.join(RUNS, "summary.json"), "w"), indent=1)
    print(json.dumps(summary["by_model"], indent=1))

    plot(runs, questions)
    write_table(summary, questions)

    if args.site:
        short = {"notebooks": "Notebooks (money)", "vans": "Vans (round up)", "movie": "Movie end time",
                 "pets": "Pets (logic)", "batball": "Bat and ball", "sheep": "Sheep (trick)",
                 "race": "Race (trick)", "strawberry": "R's in 'strawberry'", "france": "Capital of France",
                 "twoplusthree": "2 + 3"}
        meta = {
            "questions": [dict(q, short=short[q["id"]]) for q in questions],
            "models": {k: lab for k, _, _, lab, _ in MODELS},
            "summary": summary,
        }
        slim = [{k: r[k] for k in ("model", "mode", "qid", "seed", "n_thinking", "n_answer", "finished",
                                   "waits", "checks", "correct", "final", "think_end", "mismatch",
                                   "note", "thinking", "answer", "temp", "top_p", "top_k", "max_tokens")}
                for r in runs]
        os.makedirs(os.path.join(args.site, "data"), exist_ok=True)
        with open(os.path.join(args.site, "data", "traces.js"), "w") as f:
            f.write("// Real, unedited outputs from two small open models. Made by scripts/analyze.py.\n")
            f.write("window.COT_META = " + json.dumps(meta, ensure_ascii=False) + ";\n")
            f.write("window.COT_RUNS = " + json.dumps(slim, ensure_ascii=False) + ";\n")
        print("wrote", os.path.join(args.site, "data", "traces.js"))


def write_table(summary, questions):
    """LaTeX rows for the primer's per-question table, straight from summary.json."""
    short = {"notebooks": "Notebooks (money, 3 steps)", "vans": "Vans (divide, round up)",
             "movie": "Movie end time", "pets": "Pets (logic)", "batball": "Bat and ball (trick)",
             "sheep": "Sheep, all but 9 (trick)", "race": "Pass 2nd place (trick)",
             "strawberry": "R's in strawberry", "france": "Capital of France", "twoplusthree": "2 + 3"}
    bq = summary["by_question"]
    lines = []
    for q in questions:
        d = bq[q["id"]]
        r1, q3, off = d["r1"], d["q3"], d["q3off"]
        lines.append("%s & %d & %d & %d & %s & %s \\\\" % (
            short[q["id"]], r1["correct"], q3["correct"], off["correct"],
            "{:,}".format(int(round(r1["median_thinking"]))), "{:,}".format(int(round(q3["median_thinking"])))))
    tot = summary["by_model"]
    lines.append("\\midrule")
    lines.append("All 10 questions (of 30) & %d & %d & %d & %s & %s \\\\" % (
        tot["r1"]["correct"], tot["q3"]["correct"], tot["q3off"]["correct"],
        "{:,}".format(int(round(tot["r1"]["median_thinking"]))), "{:,}".format(int(round(tot["q3"]["median_thinking"])))))
    os.makedirs(FIGS, exist_ok=True)
    open(os.path.join(FIGS, "table_runs.tex"), "w").write("\n".join(lines) + "\n")
    print("wrote figs/table_runs.tex")


def plot(runs, questions):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    os.makedirs(FIGS, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5,
                         "axes.edgecolor": "#52514e", "axes.linewidth": 0.6,
                         "xtick.color": "#52514e", "ytick.color": "#52514e"})
    style = {"r1": ("#2a78d6", "o", -0.17), "q3": ("#eb6834", "s", 0.17)}
    names = {"notebooks": "Notebooks\n(money)", "vans": "Vans\n(round up)", "movie": "Movie\n(time)",
             "pets": "Pets\n(logic)", "batball": "Bat and\nball", "sheep": "Sheep\n(trick)",
             "race": "Race\n(trick)", "strawberry": "Letters in\n'strawberry'", "france": "Capital of\nFrance",
             "twoplusthree": "2 + 3"}
    fig, ax = plt.subplots(figsize=(7.0, 2.75))
    qids = [q["id"] for q in questions]
    for i in range(len(qids)):
        if i % 2 == 0:
            ax.axvspan(i - 0.5, i + 0.5, color="#f0efec", zorder=0, lw=0)
    for key, (color, marker, off) in style.items():
        mr = [r for r in runs if r["model"] == key]
        for r in mr:
            x = qids.index(r["qid"]) + off + (r["seed"] - 1) * 0.07
            y = max(r["n_thinking"], 1)
            face = color if r["correct"] else "white"
            ax.scatter([x], [y], s=34, marker=marker, facecolor=face, edgecolor=color,
                       linewidth=1.4, zorder=3)
            if not r["finished"]:
                ax.annotate("never finished (hit the 8,192-token limit)", (x, y), xytext=(x + 0.3, y * 1.45),
                            fontsize=7, color="#52514e", ha="left", va="center",
                            arrowprops=dict(arrowstyle="-", color="#8a8984", lw=0.6))
    ax.set_yscale("log")
    ax.set_ylim(20, 14000)
    ax.set_yticks([30, 100, 300, 1000, 3000, 10000])
    ax.set_yticklabels(["30", "100", "300", "1,000", "3,000", "10,000"])
    ax.set_ylabel("Thinking length (tokens)")
    ax.set_xticks(range(len(qids)))
    ax.set_xticklabels([names[q] for q in qids], fontsize=7.2)
    ax.set_xlim(-0.5, len(qids) - 0.5)
    ax.grid(axis="y", color="#dcdbd5", lw=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    handles = [
        Line2D([], [], marker="o", ls="", color="#2a78d6", markersize=6, label="DeepSeek-R1-Distill-Qwen-1.5B"),
        Line2D([], [], marker="s", ls="", color="#eb6834", markersize=6, label="Qwen3-1.7B"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor="#52514e",
               markersize=6, label="hollow = wrong or no answer"),
    ]
    ax.legend(handles=handles, loc="upper left", ncol=3, frameon=False, fontsize=7.4,
              bbox_to_anchor=(0, 1.13), handletextpad=0.3, columnspacing=1.2)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGS, "fig_tokens." + ext), dpi=200)
    plt.close(fig)
    print("wrote figs/fig_tokens.pdf")


if __name__ == "__main__":
    main()
