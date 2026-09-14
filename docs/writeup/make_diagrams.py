"""Generate the two explanatory diagrams for the Strategy Category writeup:
1) the confidence-ladder decision architecture
2) the deck concept map (why each card is in the 60)
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
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
BLUE_L = "#cde2fb"
ORANGE = "#eb6834"
ORANGE_L = "#fbe0d4"
AQUA = "#1baf7a"
AQUA_L = "#cdeee0"
YELLOW = "#eda100"
YELLOW_L = "#fbe8c7"

plt.rcParams["font.family"] = "DejaVu Sans"


def box(ax, xy, w, h, text, fc, ec, tcolor=INK, fs=10, weight="normal", radius=0.06):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.0,rounding_size={radius}",
                        linewidth=1.3, edgecolor=ec, facecolor=fc, zorder=3)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=tcolor, weight=weight, zorder=4, linespacing=1.35)


def arrow(ax, p0, p1, color=MUTED):
    a = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13,
                         linewidth=1.4, color=color, zorder=2, shrinkA=2, shrinkB=2)
    ax.add_patch(a)


# ---------------------------------------------------------------------------
# Diagram 1: confidence-ladder architecture
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.6, 7.0), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_xlim(0, 10)
ax.set_ylim(2.4, 13.2)
ax.axis("off")

ax.text(0.1, 12.75, "The confidence ladder: match the tool to how certain the decision is",
        fontsize=13.5, weight="bold", color=INK)
ax.text(0.1, 12.25, "Rules rank every candidate; search re-checks the choice only where its gate is met, the evaluator scores unfinished continuations.",
        fontsize=9.3, color=INK2)

row_h = 1.4
gap = 0.5
top = 10.5
rows = [
    dict(fc=BLUE_L, ec=BLUE, tag="1 · Deterministic math",
         body="Deck-out and Prize race estimated\nfrom card counts and observed pace",
         tool="Rule-based accounting\n(no search)"),
    dict(fc=AQUA_L, ec=AQUA, tag="2 · Near-perfect info",
         body="Endgame: either deck ≤ 14 cards;\nhidden information barely matters",
         tool="Let the search play it\nout (endgame PUCT)"),
    dict(fc=ORANGE_L, ec=ORANGE, tag="3 · Genuinely uncertain",
         body="Mid-game board state with real\nhidden information on both sides",
         tool="Learned evaluator scores\nunfinished continuations"),
    dict(fc=YELLOW_L, ec=YELLOW, tag="4 · Strategic macro-choice",
         body="Race for prizes vs. race for\nthe opponent's deck-out",
         tool="Discrete rule flag,\nnot a learned continuum"),
]

for i, r in enumerate(rows):
    y = top - i * (row_h + gap)
    box(ax, (0.1, y), 3.0, row_h, r["tag"], "#ffffff", r["ec"], tcolor=INK, fs=9.2, weight="bold", radius=0.08)
    box(ax, (3.35, y), 3.5, row_h, r["body"], r["fc"], r["ec"], fs=8.3)
    box(ax, (7.1, y), 2.8, row_h, r["tool"], "#ffffff", r["ec"], fs=8.6, weight="bold")

last_row_y = top - (len(rows) - 1) * (row_h + gap)
footer_y = last_row_y - 0.45
ax.text(0.1, footer_y,
        "Layers 1 and 4 are rules and stay inspectable; the learned evaluator scores unfinished\n"
        "continuations in layers 2 and 3. Three rejected upgrades (GBDT, policy clone, value net)\n"
        "all targeted the evaluator and none improved our benchmark in controlled A/B tests.\n"
        "The one confirmed win in our league, endgame PUCT, targeted layer 2: restructuring\n"
        "search where hidden information is smallest.",
        fontsize=8.6, color=INK2, linespacing=1.6, va="top")

fig.savefig(os.path.join(OUT, "04_confidence_ladder.png"), facecolor=SURFACE, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)


# ---------------------------------------------------------------------------
# Diagram 2: deck concept map
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(8.6, 6.9), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_xlim(0, 10)
ax.set_ylim(0, 8.6)
ax.axis("off")

ax.text(0.1, 8.25, "Deck concept: win the deck-out race the opponent can't see coming",
        fontsize=13.2, weight="bold", color=INK)
ax.text(0.1, 7.8, "60 cards, four jobs. No card is in the list without one of these four jobs.",
        fontsize=9.3, color=INK2)

# Column boxes (four jobs)
cols = [
    dict(x=0.1, fc=BLUE_L, ec=BLUE, title="Real damage,\ncheap to give up",
         body="Great Tusk ×4 — Basic,\n140 HP. Land Collapse\nmills 1–4 cards a turn;\nGiant Tusk hits 160.\nNon-Rule-Box: only\n1 Prize to KO it."),
    dict(x=2.55, fc=AQUA_L, ec=AQUA, title="A wall that\nsearches itself",
         body="Dwebble ×4 → Crustle ×4.\nAscension tutors the\nevolution from the deck\n(thins it).\nCrustle: ex attacks\ndo no damage; 120 dmg\nignores effects on\nthe Active."),
    dict(x=5.0, fc=ORANGE_L, ec=ORANGE, title="Take away their\nturn, not their HP",
         body="Crushing Hammer ×2\n(energy denial), Xerosic's\nMachinations ×2 (hand\nto 3), Budew ×1 (Item\nlock), Jumbo Ice Cream\n×2 (heal 80)."),
    dict(x=7.45, fc=YELLOW_L, ec=YELLOW, title="Make their ex/V\nswing for nothing",
         body="Neutralization Zone ×1\n(ACE SPEC): no damage\nfrom ex/V attacks to\nnon-Rule-Box Pokémon.\nRock Fighting ×4, Mist\n×2; Battle Cage ×2."),
]

for c in cols:
    box(ax, (c["x"], 6.1), 2.2, 1.55, c["title"], "#ffffff", c["ec"], fs=9.6, weight="bold", radius=0.09)
    box(ax, (c["x"], 3.55), 2.2, 2.35, c["body"], c["fc"], c["ec"], fs=7.6)
    arrow(ax, (c["x"] + 1.1, 6.1), (c["x"] + 1.1, 5.9))

# convergence arrow to outcome box
for c in cols:
    arrow(ax, (c["x"] + 1.1, 3.55), (5.0, 2.5), color=MUTED)

box(ax, (1.4, 1.15), 7.2, 1.35,
    "Outcome: the opponent runs out of deck\nbefore Great Tusk and Crustle run out of ways to survive",
    "#ffffff", INK2, fs=9.2, weight="bold", radius=0.1)

ax.text(0.1, 0.75,
        "Support engine (Poké Pad, Explorer's Guidance, Lillie's Determination, Counter Gain, Switch,\n"
        "Boss's Orders, Buddy-Buddy Poffin, Night Stretcher, Pokégear 3.0) keeps all four jobs on schedule —\n"
        "every turn's search target is (ideal board for the current plan) minus (board + hand), not\n"
        "hand-written per matchup.",
        fontsize=7.7, color=INK2, linespacing=1.6, va="top")

fig.savefig(os.path.join(OUT, "05_deck_concept.png"), facecolor=SURFACE, bbox_inches="tight", pad_inches=0.25)
plt.close(fig)

print("wrote", sorted(os.listdir(OUT)))
