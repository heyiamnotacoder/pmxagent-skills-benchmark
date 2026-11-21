#!/usr/bin/env python3
"""Paper figures from results/scores.csv + results/runs.csv -> paper/figures/*.pdf (+ .png preview).

fig_params_<task>: per-parameter accuracy (% within 1% of PKanalix), mean over runs, one marker per arm.
fig_cost_<task>:   overall accuracy vs notional cost per run (mean ± SD), direct-labelled.
Colours: validated categorical palette (dataviz skill, light mode); every arm also has its own marker shape and a
direct label, so identity never relies on colour alone.  Usage: figures.py [--task T1_nca]
"""
import argparse, csv, os, statistics as st
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
OUT = os.path.join(ROOT, "paper", "figures")
ARMS = ["A0", "A1", "A1b", "A2", "A3", "A4"]
LABEL = {"A0": "A0 no tools", "A1": "A1 PMxAgent (MCP)", "A1b": "A1b PMxAgent (MCP + CLAUDE.md)",
         "A2": "A2 Skills, knowledge only", "A3": "A3 Skills + script", "A4": "A4 Skills + script, Haiku"}
COLOR = {"A0": "#2a78d6", "A1": "#eb6834", "A1b": "#7a5195", "A2": "#1baf7a", "A3": "#eda100", "A4": "#e87ba4"}
MARK = {"A0": "o", "A1": "s", "A1b": "P", "A2": "D", "A3": "^", "A4": "v"}
PARAMS = [("Cmax", "Cmax"), ("Tmax", "Tmax"), ("AUClast", "AUClast"), ("AUCINF_obs", "AUCINF,obs"),
          ("HL", "t½"), ("CL", "CL(/F)"), ("Vz", "Vz(/F)")]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e6e5e1", "#ffffff"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.dpi": 300})


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), bbox_inches="tight")
    plt.close(fig)
    print("wrote", os.path.join("paper", "figures", name + ".pdf"))


def fig_params(scores, task):
    arms = [a for a in ARMS if scores[a]]
    fig, ax = plt.subplots(figsize=(6.3, 3.0))
    off = {a: (i - (len(arms) - 1) / 2) * 0.14 for i, a in enumerate(arms)}
    for j, (p, _) in enumerate(PARAMS):
        ax.axhline(j, color=GRID, lw=0.6, zorder=0)
        for a in arms:
            v = [f(r[f"{p}_pct"]) for r in scores[a] if f(r.get(f"{p}_pct")) is not None]
            if v:
                ax.scatter(st.mean(v), j + off[a], s=30, marker=MARK[a], color=COLOR[a], edgecolor=SURF,
                           linewidth=0.8, zorder=3, label=LABEL[a] if j == 0 else None)
    ax.set_yticks(range(len(PARAMS)), [lab for _, lab in PARAMS])
    ax.invert_yaxis()
    ax.set_xlim(80, 100.5)
    ax.set_xlabel("Subjects within 1% of PKanalix (%), mean over runs")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=3, fontsize=7,
              handletextpad=0.3, columnspacing=1.2)
    save(fig, f"fig_params_{task}")


def fig_cost(scores, runs, task):
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for a in ARMS:
        acc = [f(r["overall"]) for r in scores[a] if f(r.get("overall")) is not None]
        cost = [f(runs[r["runid"]]["cost_usd"]) for r in scores[a] if r["runid"] in runs]
        cost = [c for c in cost if c is not None]
        if not acc or not cost:
            continue
        mx, my = st.mean(cost), st.mean(acc)
        sx = st.stdev(cost) if len(cost) > 1 else 0
        sy = st.stdev(acc) if len(acc) > 1 else 0
        ax.errorbar(mx, my, xerr=sx, yerr=sy, fmt="none", ecolor=COLOR[a], elinewidth=1.0, capsize=0, zorder=2)
        ax.scatter(mx, my, s=34, marker=MARK[a], color=COLOR[a], edgecolor=SURF, linewidth=0.8, zorder=3)
        above = a in ("A0", "A1b", "A2", "A4")   # alternate label side so neighbours never collide
        ax.annotate(f"{a} (n={len(acc)})", (mx, my), xytext=(0, 8 if above else -13), textcoords="offset points",
                    ha="center", fontsize=7, color=INK)
    ax.set_xlabel("Cost per run (USD, list-price estimate)")
    ax.set_ylabel("Overall accuracy (%)")
    ax.set_xlim(left=0)
    ax.margins(y=0.1)   # headroom for the direct labels
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    save(fig, f"fig_cost_{task}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="T1_nca")
    a = ap.parse_args()
    scores = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(RES, "scores.csv"))):
        if r["task"] == a.task:
            scores[r["arm"]].append(r)
    runs = {r["runid"]: r for r in csv.DictReader(open(os.path.join(RES, "runs.csv")))}
    fig_params(scores, a.task)
    fig_cost(scores, runs, a.task)


if __name__ == "__main__":
    main()
