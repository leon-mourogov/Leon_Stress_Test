"""pdf.py — rapport de 2 pages avec matplotlib (PdfPages)."""

import matplotlib

matplotlib.use("Agg")  # aucun écran : le job tourne sans session graphique
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from quantlab.storage import metric_history  # noqa: E402

BLUE, CRITICAL, INK, MUTED, GRID = "#2a78d6", "#d03b3b", "#0b0b0b", "#52514e", "#e4e3df"
A4 = (8.27, 11.69)


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def _eur(x):
    return f"{x:,.0f} €".replace(",", " ")


def _page1(pdf, ctx):
    d = ctx.data
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.95, f"Rapport de risque — {ctx.as_of:%d/%m/%Y}", fontsize=16, weight="bold", color=INK)
    if ctx.status != "OK":
        fig.text(
            0.07,
            0.915,
            "INCOMPLET : " + " ; ".join(ctx.warnings),
            fontsize=9,
            color=CRITICAL,
            weight="bold",
            wrap=True,
        )
    # tableau des limites
    ax = fig.add_axes([0.07, 0.68, 0.86, 0.2])
    ax.axis("off")
    lu = d["limits_usage"]
    cells = [
        [
            k,
            _eur(r.valeur),
            _eur(r.limite),
            f"{r.utilisation:.0%}",
            "DÉPASSEMENT" if r.utilisation > 1 else "ok",
        ]
        for k, r in lu.iterrows()
    ]
    if "var" not in d:
        cells += [[k, "non calculée", "", "", "INCOMPLET"] for k in ("var99", "es975")]
    table = ax.table(
        cellText=cells,
        colLabels=["Indicateur", "Valeur", "Limite", "Utilisation", "État"],
        loc="upper left",
        cellLoc="right",
        colLoc="right",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)
    for (r, _c), cell in table.get_celld().items():
        cell.set_edgecolor(GRID)
        if r > 0 and cells[r - 1][4] in ("DÉPASSEMENT", "INCOMPLET"):
            cell.get_text().set_color(CRITICAL)
            cell.get_text().set_weight("bold")
    # stress : P&L total par scénario, trié
    ax = fig.add_axes([0.32, 0.1, 0.6, 0.5])
    tot = d["stress"]["TOTAL"].drop("Base").sort_values()
    ax.barh(tot.index, tot.values, color=BLUE, height=0.6)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    for y, v in enumerate(tot.values):
        ax.text(
            v, y, " " + _eur(v) + " ", va="center", ha="left" if v >= 0 else "right", fontsize=8, color=INK
        )
    lim = ctx.data["limits"].get("stress_worst")
    if lim:
        ax.axvline(-lim, color=CRITICAL, linewidth=1, linestyle="--")
        ax.text(-lim, -0.75, f" limite −{_eur(lim)}", color=CRITICAL, fontsize=8, ha="left", va="top")
    ax.set_title("P&L du book par scénario de stress (EUR)", loc="left", fontsize=11, color=INK)
    lo, hi = min(tot.min(), -(lim or 0)), max(tot.max(), 0)
    ax.set_xlim(lo * 1.45, hi * 1.45 if hi > 0 else abs(lo) * 0.2)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x / 1000:,.0f} k")
    _style(ax)
    pdf.savefig(fig)
    plt.close(fig)


def _page2(pdf, ctx):
    d = ctx.data
    fig = plt.figure(figsize=A4)
    fig.text(0.07, 0.95, "VaR historique", fontsize=14, weight="bold", color=INK)
    ax = fig.add_axes([0.1, 0.58, 0.82, 0.3])
    if "var_pnl" in d:
        pnl, var = d["var_pnl"], d["var"]["var99"]
        ax.hist(pnl / 1000, bins=50, color=BLUE, edgecolor="white", linewidth=0.5)
        ax.axvline(-var / 1000, color=CRITICAL, linewidth=1.2)
        ax.text(-var / 1000, ax.get_ylim()[1] * 0.9, f" VaR 99 % = {_eur(var)}", color=CRITICAL, fontsize=8)
        ax.set_title(
            f"Distribution du P&L 1 jour ({len(pnl)} scénarios historiques, k€)", loc="left", fontsize=11
        )
    else:
        ax.axis("off")
        ax.text(0, 0.5, "VaR non calculée : voir les avertissements page 1.", color=CRITICAL, fontsize=11)
    _style(ax)
    ax = fig.add_axes([0.1, 0.12, 0.82, 0.32])
    hist = metric_history(d["engine"], "var99", ctx.as_of, days=30)
    if len(hist) >= 2:
        ax.plot(hist.index, hist.values / 1000, color=BLUE, linewidth=2, marker="o", markersize=4)
        lim = ctx.data["limits"].get("var99")
        if lim:
            ax.axhline(lim / 1000, color=CRITICAL, linewidth=1, linestyle="--")
            ax.text(hist.index[0], lim / 1000, " limite", color=CRITICAL, fontsize=8, va="bottom")
        ax.set_ylim(0, max(hist.max(), lim or 0) / 1000 * 1.15)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        fig.autofmt_xdate()
    else:
        ax.axis("off")
        ax.text(0.0, 0.5, "Historique insuffisant (moins de 2 jours en base).", fontsize=10, color=MUTED)
    ax.set_title("VaR 99 % 1 jour sur les 30 derniers rapports (k€)", loc="left", fontsize=11)
    _style(ax)
    pdf.savefig(fig)
    plt.close(fig)


def write_pdf(ctx):
    path = ctx.out_dir / f"risk_report_{ctx.as_of:%Y%m%d}.pdf"
    with PdfPages(path) as pdf:
        _page1(pdf, ctx)
        _page2(pdf, ctx)
    return path
