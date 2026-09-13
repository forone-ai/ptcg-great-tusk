"""Generate Media Gallery figures for the Strategy Category writeup.

Static PNGs only (Kaggle Writeup media gallery takes images/video, not
interactive HTML). Palette follows the dataviz skill's validated default
(references/palette.md): blue as primary sequential/series-1 hue, chart
surface #fcfcfb, primary ink #0b0b0b, secondary ink #52514e, muted #898781,
gridline #e1e0d9.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
import os

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
GOOD = "#0ca30c"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["text.color"] = INK
plt.rcParams["axes.edgecolor"] = BASELINE
plt.rcParams["axes.labelcolor"] = INK2
plt.rcParams["xtick.color"] = MUTED
plt.rcParams["ytick.color"] = MUTED


def style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.spines["bottom"].set_linewidth(1)
    ax.grid(axis="y", color=GRID, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


# ---------------------------------------------------------------------------
# Chart 1: League win-rate milestones (rule plateau -> search breakthrough
# -> current submission), internal 15-agent proxy league.
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
fig.patch.set_facecolor(SURFACE)

stages = [
    "Pre-project\nrule baseline",
    "Rule-only\nplateau\n(~40 versions)",
    "+ Search API\n(v26, teacher-\ndistilled rollout)",
    "weakmath_v1\n(human-review\nloop, n=1632)",
    "#10 / #11\n(endgame PUCT +\nstructural fixes)",
]
values = [47.2, 48.7, 67.2, 71.2, 76.6]
x = list(range(len(stages)))

ax.plot(x, values, color=BLUE, linewidth=2, zorder=3, solid_capstyle="round")
ax.scatter(x, values, s=46, color=BLUE, zorder=4, edgecolor=SURFACE, linewidth=1.5)

for xi, yi in zip(x, values):
    ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 10),
                ha="center", fontsize=10.5, color=INK, fontweight="bold")

ax.set_xticks(x)
ax.set_xticklabels(stages, fontsize=8.6, color=INK2)
ax.set_ylim(35, 85)
ax.set_ylabel("Win rate — internal proxy league", fontsize=10)
style_ax(ax)
ax.set_title("From a 48.7% rule ceiling to a search-and-review pipeline",
             fontsize=12.5, color=INK, fontweight="bold", loc="left", pad=14)
fig.text(0.01, 0.025,
         "Internal offline benchmark against a fixed 15-agent proxy league (public rule-based +\n"
         "replay-derived agents), single-threaded isolated runs. Not an official Kaggle leaderboard score.",
         fontsize=7.3, color=MUTED, linespacing=1.5)
fig.tight_layout(rect=[0, 0.09, 1, 1])
fig.savefig(os.path.join(OUT, "01_league_progression.png"), facecolor=SURFACE)
plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 2: hardest-matchup trajectory (dark-hand-disruption wall archetype)
# across submissions.
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=200)
fig.patch.set_facecolor(SURFACE)

subs = ["#5\n(7/28)", "#7\n(7/31)", "#9\n(8/2)", "#10\n(8/3)", "#11\n(8/4)"]
wr = [43.8, 52.9, 53.3, 60.2, 63.7]
x = list(range(len(subs)))

bars = ax.bar(x, wr, width=0.5, color=BLUE, zorder=3)
for xi, yi in zip(x, wr):
    ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 6),
                ha="center", fontsize=10.5, color=INK, fontweight="bold")

ax.axhline(53, color=MUTED, linewidth=1, linestyle=(0, (3, 3)), zorder=2)
ax.annotate("pre-project ceiling\non this matchup", (4.35, 53), va="center", ha="left",
            fontsize=7.6, color=MUTED, linespacing=1.3)
ax.set_xlim(-0.6, 5.3)

ax.set_xticks(x)
ax.set_xticklabels(subs, fontsize=9.5, color=INK2)
ax.set_ylim(0, 75)
ax.set_ylabel("Win rate vs. Grimmsnarl disruption\n(the toughest matchup, current meta's #1 archetype)", fontsize=9.5)
style_ax(ax)
ax.set_title("Closing the gap against Grimmsnarl disruption",
             fontsize=12.5, color=INK, fontweight="bold", loc="left", pad=14)
fig.text(0.01, 0.025,
         "Submission-gate benchmark, single-threaded isolated runs (n=192-640 per point). Each step corresponds\n"
         "to a specific human-replay-reviewed fix, not a blanket parameter search.",
         fontsize=7.3, color=MUTED, linespacing=1.5)
fig.tight_layout(rect=[0, 0.09, 1, 1])
fig.savefig(os.path.join(OUT, "02_hardest_matchup.png"), facecolor=SURFACE)
plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 3: matchup breakdown by opponent archetype (latest confirmed line).
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
fig.patch.set_facecolor(SURFACE)

archetypes = [
    "Grimmsnarl\ndisruption\n(current #1 meta)",
    "Fighting /\nex aggro",
    "Deck-out\nmirror",
    "Alakazam\nex control",
]
wr = [63.7, 77.9, 50.5, 39.8]
colors = [BLUE, ORANGE, AQUA, YELLOW]
x = list(range(len(archetypes)))

ax.bar(x, wr, width=0.55, color=colors, zorder=3)
for xi, yi in zip(x, wr):
    ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 6),
                ha="center", fontsize=10.5, color=INK, fontweight="bold")

ax.axhline(50, color=MUTED, linewidth=1, linestyle=(0, (3, 3)), zorder=2)
ax.set_xticks(x)
ax.set_xticklabels(archetypes, fontsize=9.0, color=INK2)
ax.set_ylim(0, 90)
ax.set_ylabel("Win rate by opponent archetype", fontsize=10)
style_ax(ax)
ax.set_title("Where the deck is strong, even, and still working (#11)",
             fontsize=12.5, color=INK, fontweight="bold", loc="left", pad=14)
fig.text(0.01, 0.025,
         "Latest submission-gate benchmark (n=192+ per archetype, single-threaded). Alakazam ex control is the\n"
         "open item, tracked down -4.7pt vs. the prior submission: our best working hypothesis is a stadium\n"
         "war (see write-up) that removes our damage-nullifying tech before it can stick.",
         fontsize=7.1, color=MUTED, linespacing=1.5)
fig.tight_layout(rect=[0, 0.11, 1, 1])
fig.savefig(os.path.join(OUT, "03_matchup_breakdown.png"), facecolor=SURFACE)
plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 6: meta evolution timeline. Two anchor points are quantified
# (community discussion analysis of 74,634 games); the earlier eras are
# qualitative only and are drawn as unlabeled-height bands, not invented
# numbers.
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.0, 4.3), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_xlim(0, 10)
ax.set_ylim(0, 6.4)
ax.axis("off")

ax.text(0.0, 6.05, "The meta the deck had to track, not just the meta it was designed against",
        fontsize=12.3, color=INK, fontweight="bold")
ax.text(0.0, 5.62,
        "Leading archetype among top-ranked public decks over the project's first six weeks.",
        fontsize=9.2, color=INK2)

track_y = 3.1
track_h = 1.5
eras = [
    dict(x0=0.0, x1=2.05, fc="#e7e4d9", ec=BASELINE, label="June\nCrustle /\nMega Lucario wall", quant=False),
    dict(x0=2.15, x1=3.55, fc="#e7e4d9", ec=BASELINE, label="early Jul\nArchaludon", quant=False),
    dict(x0=3.65, x1=6.0, fc=ORANGE, ec=ORANGE, label="mid Jul\nAlakazam\n(Telepath) control", quant=True, pt=(5.5, "46%", "peak, 7/14")),
    dict(x0=6.1, x1=10.0, fc=BLUE, ec=BLUE, label="7/17 → 7/26\nGrimmsnarl disruption", quant=True, pt=(9.6, "51.3%", "of top ranks, 7/26")),
]

for e in eras:
    alpha = 1.0 if e["quant"] else 0.55
    ax.add_patch(plt.Rectangle((e["x0"], track_y), e["x1"] - e["x0"], track_h,
                                facecolor=e["fc"], edgecolor=e["ec"], linewidth=1.2,
                                alpha=alpha, zorder=2))
    ax.text((e["x0"] + e["x1"]) / 2, track_y + track_h / 2, e["label"],
            ha="center", va="center", fontsize=7.6,
            color=(INK if e["quant"] else INK2), fontweight=("bold" if e["quant"] else "normal"),
            linespacing=1.45, zorder=3)

for e in eras:
    if e.get("quant"):
        px, pct, sub = e["pt"]
        ax.plot([px], [track_y - 0.22], marker="v", color=INK, markersize=7, zorder=4)
        ax.text(px, track_y - 0.42, pct, ha="center", va="top", fontsize=11.5, color=INK, fontweight="bold")
        ax.text(px, track_y - 0.82, sub, ha="center", va="top", fontsize=7.6, color=MUTED)

ax.text(0.0, 1.05,
        "Only the two dark callouts are quantified in the source; June/early-July shares are directional only\n"
        "(not independently measured) — shown lighter deliberately. Source: community analysis of 74,634\n"
        "ranked games (Kaggle discussion #729926). Our own gates already track Grimmsnarl as the primary\n"
        "benchmark opponent, so the deck's evidence base moved with the meta rather than chasing it after the fact.",
        fontsize=7.6, color=INK2, linespacing=1.6, va="top")

fig.savefig(os.path.join(OUT, "06_meta_shift.png"), facecolor=SURFACE, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)

print("wrote", sorted(os.listdir(OUT)))
