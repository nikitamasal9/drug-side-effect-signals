"""Static PNG charts for the README (the interactive version lives in the dashboard)."""
import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import DB_PATH, OUTPUTS

BLUE, MUTED, RED, INK, GRID = "#2a78d6", "#b9b8b2", "#e34948", "#0b0b0b", "#e7e6e2"


def _style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors="#52514e", labelsize=9, length=0)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def known_effects(con, path):
    df = (con.execute("SELECT * FROM an_known_effect_check WHERE pct_in_class IS NOT NULL").df()
          .assign(gap=lambda d: d.pct_in_class - d.pct_outside_class).sort_values("gap"))
    labels = df.class_label + " · " + df.side_effect_name
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(df) + 1.2), dpi=150)
    y = range(len(df))
    ax.hlines(y, df.pct_outside_class, df.pct_in_class, color=MUTED, linewidth=2)
    ax.scatter(df.pct_outside_class, y, s=40, color=MUTED, zorder=3, label="All other drugs")
    colors = [BLUE if s == "recovered" else RED for s in df.status]
    ax.scatter(df.pct_in_class, y, s=46, color=colors, zorder=4, label="Drugs in class")
    ax.set_yticks(list(y), labels, fontsize=9, color=INK)
    ax.set_xlim(0, 1.02)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    _style(ax)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=BLUE, label="Drugs in class (recovered)"),
               Line2D([], [], marker="o", ls="", color=RED, label="Drugs in class (not significant)"),
               Line2D([], [], marker="o", ls="", color=MUTED, label="All other drugs")]
    fig.suptitle("Known class effects: share of drugs listing the side effect", x=0.01, ha="left", fontsize=11, color=INK)
    fig.legend(handles=handles, frameon=False, fontsize=8, ncol=3, loc="upper left", bbox_to_anchor=(0.01, 0.955))
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path)
    plt.close(fig)


def funnel(con, path):
    df = con.execute("SELECT * FROM an_q01_data_funnel ORDER BY step DESC").df()
    fig, ax = plt.subplots(figsize=(8, 2.8), dpi=150)
    ax.barh(df.stage, df.n, color=[BLUE] * (len(df) - 1) + [MUTED], height=0.6)
    for i, v in enumerate(df.n):
        ax.text(v + 15, i, f"{v:,}", va="center", fontsize=9, color="#52514e")
    ax.tick_params(axis="y", labelsize=9)
    _style(ax)
    ax.set_xlim(0, df.n.max() * 1.12)
    fig.suptitle("Data surviving each merge step", x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(con=None):
    con = con or duckdb.connect(str(DB_PATH), read_only=True)
    (OUTPUTS / "figures").mkdir(parents=True, exist_ok=True)
    known_effects(con, OUTPUTS / "figures" / "known_class_effects.png")
    funnel(con, OUTPUTS / "figures" / "data_funnel.png")
    print("  wrote README figures to outputs/figures/")


if __name__ == "__main__":
    main()
