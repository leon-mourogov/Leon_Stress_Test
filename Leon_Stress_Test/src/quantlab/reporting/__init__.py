"""reporting — fichiers de sortie du rapport quotidien : Excel multi-onglets et PDF de 2 pages."""

from quantlab.reporting.excel import write_excel
from quantlab.reporting.pdf import write_pdf


def write_reports(ctx):
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    return [write_excel(ctx), write_pdf(ctx)]
