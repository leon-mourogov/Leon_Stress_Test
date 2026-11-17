"""excel.py — classeur multi-onglets mis en forme avec openpyxl."""

import pandas as pd
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

RED = PatternFill("solid", fgColor="F4C7C3")
HEADER = PatternFill("solid", fgColor="DCE6F2")
EUR = "#,##0;[Red]-#,##0"


def _summary(ctx):
    rows = [
        ("Date de marché", ctx.as_of.isoformat()),
        ("Statut", "COMPLET" if ctx.status == "OK" else "INCOMPLET"),
    ]
    rows += [("Avertissement", w) for w in ctx.warnings]
    m = ctx.data.get("metrics", {})
    labels = {"var99": "VaR 99 % 1 jour", "es975": "ES 97,5 % 1 jour", "stress_worst": "Pire stress"}
    rows += [(labels.get(k, k), round(v)) for k, v in m.items()]
    return pd.DataFrame(rows, columns=["Indicateur", "Valeur"]).set_index("Indicateur")


def _format_sheet(ws, money_cols=(), pct_cols=()):
    ws.freeze_panes = "B2"  # en-tête et première colonne toujours visibles
    for cell in ws[1]:
        cell.font, cell.fill = Font(bold=True), HEADER
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    for col in ws.iter_cols(min_row=2):
        name = ws.cell(row=1, column=col[0].column).value
        for cell in col:
            if name in money_cols:
                cell.number_format = EUR
            elif name in pct_cols:
                cell.number_format = "0.0%"
    for i, col in enumerate(ws.columns, start=1):
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max(10, width + 2), 60)


def write_excel(ctx):
    path = ctx.out_dir / f"risk_report_{ctx.as_of:%Y%m%d}.xlsx"
    d = ctx.data
    sheets = {"Synthese": _summary(ctx)}
    if "limits_usage" in d:
        sheets["Limites"] = d["limits_usage"]
    sheets["Positions"] = d["valuation"]
    sheets["Stress"] = d["stress"]
    if "var_pnl" in d:
        sheets["VaR_PnL"] = d["var_pnl"].rename_axis("scenario").to_frame()
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name)
        wb = xw.book
        _format_sheet(wb["Synthese"])
        if ctx.status != "OK":
            wb["Synthese"]["B3"].fill = RED
            wb["Synthese"]["B3"].font = Font(bold=True, color="9C0006")
        if "Limites" in wb.sheetnames:
            ws = wb["Limites"]
            _format_sheet(ws, money_cols=("valeur", "limite"), pct_cols=("utilisation",))
            ws.conditional_formatting.add(
                f"D2:D{ws.max_row}", CellIsRule(operator="greaterThan", formula=["1"], fill=RED)
            )
        _format_sheet(wb["Positions"], money_cols=("valeur_eur",))
        _format_sheet(wb["Stress"], money_cols=tuple(d["stress"].columns))
        if "VaR_PnL" in wb.sheetnames:
            _format_sheet(wb["VaR_PnL"], money_cols=("pnl",))
    return path
