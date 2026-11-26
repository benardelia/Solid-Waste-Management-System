"""Render a ReportResult into CSV, XLSX, PDF or JSON bytes."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal

from django.utils import timezone

from .registry import Column, ReportResult

FORMATS = {
    'csv': ('text/csv; charset=utf-8', 'csv'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'),
    'pdf': ('application/pdf', 'pdf'),
    'json': ('application/json', 'json'),
}

ORG_NAME = 'Solid Waste Management System'


def display(value, kind: str) -> str:
    """Human-readable cell text (used by CSV, PDF and the GraphQL preview)."""
    if value is None or value == '':
        return ''
    if kind == 'money':
        return f"{Decimal(value):,.0f}"
    if kind == 'percent':
        return f"{value}%"
    if kind == 'number':
        return f"{value:,}" if isinstance(value, int) else str(value)
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def to_csv(result: ReportResult) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([c.label for c in result.columns])
    for row in result.rows:
        # Raw numbers in CSV so spreadsheets can sum them.
        writer.writerow([
            json_value(row.get(c.key)) if c.kind in ('money', 'number', 'percent') else display(row.get(c.key), c.kind)
            for c in result.columns
        ])
    # BOM so Excel opens UTF-8 (Swahili names, en-dashes) correctly.
    return ('﻿' + buf.getvalue()).encode('utf-8')


def to_json(result: ReportResult) -> bytes:
    payload = {
        'title': result.title,
        'subtitle': result.subtitle,
        'generated_at': timezone.now().isoformat(),
        'columns': [{'key': c.key, 'label': c.label, 'kind': c.kind} for c in result.columns],
        'summary': [{'label': l, 'value': v} for l, v in result.summary],
        'rows': [{c.key: json_value(r.get(c.key)) for c in result.columns} for r in result.rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')


def to_xlsx(result: ReportResult) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = result.title[:31]
    header_fill = PatternFill('solid', fgColor='1F5F4A')

    ws.append([result.title])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([result.subtitle])
    ws.append([f"Generated {timezone.localtime():%d %b %Y %H:%M}"])
    ws.append([])
    header_row = ws.max_row + 1
    ws.append([c.label for c in result.columns])
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(vertical='center')

    formats = {'money': '#,##0', 'number': '#,##0', 'percent': '0.0"%"',
               'date': 'yyyy-mm-dd', 'datetime': 'yyyy-mm-dd hh:mm'}
    for row in result.rows:
        values = []
        for c in result.columns:
            v = row.get(c.key)
            if isinstance(v, Decimal):
                v = float(v)
            if isinstance(v, datetime) and v.tzinfo:
                v = timezone.localtime(v).replace(tzinfo=None)  # Excel has no timezones
            values.append(v)
        ws.append(values)
        for cell, c in zip(ws[ws.max_row], result.columns):
            if c.kind in formats:
                cell.number_format = formats[c.kind]

    for idx, c in enumerate(result.columns, start=1):
        longest = max([len(c.label)] + [len(display(r.get(c.key), c.kind)) for r in result.rows[:500]])
        ws.column_dimensions[get_column_letter(idx)].width = min(max(longest + 2, 10), 45)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    if result.rows:
        ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(result.columns))}{ws.max_row}"

    if result.summary:
        summary = wb.create_sheet('Summary')
        summary.append(['Metric', 'Value'])
        for cell in summary[1]:
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = header_fill
        for label, value in result.summary:
            summary.append([label, value])
        summary.column_dimensions['A'].width = 30
        summary.column_dimensions['B'].width = 25

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def to_pdf(result: ReportResult) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    wide = len(result.columns) > 6
    pagesize = landscape(A4) if wide else A4
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize, title=result.title, author=ORG_NAME,
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle('cell', parent=styles['Normal'], fontSize=7.5, leading=9)
    head_style = ParagraphStyle('head', parent=cell_style, textColor=colors.white, fontName='Helvetica-Bold')
    num_style = ParagraphStyle('num', parent=cell_style, alignment=2)
    head_num_style = ParagraphStyle('head_num', parent=head_style, alignment=2)
    brand = colors.HexColor('#1F5F4A')

    story = [
        Paragraph(ORG_NAME, ParagraphStyle('org', parent=styles['Normal'], textColor=colors.grey, fontSize=9)),
        Paragraph(result.title, ParagraphStyle('t', parent=styles['Title'], alignment=0, fontSize=17, spaceAfter=2)),
        Paragraph(result.subtitle, ParagraphStyle('s', parent=styles['Normal'], textColor=colors.grey)),
        Spacer(1, 5 * mm),
    ]

    if result.summary:
        cells = [[Paragraph(f"<font size=7 color='#6b7280'>{l.upper()}</font><br/><b>{v}</b>", cell_style)
                  for l, v in result.summary[i:i + 4]] for i in range(0, len(result.summary), 4)]
        for row in cells:
            row += [''] * (4 - len(row))
        summary = Table(cells, colWidths=[(pagesize[0] - 24 * mm) / 4] * 4, hAlign='LEFT')
        summary.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F3')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#D5DED9')),
            ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story += [summary, Spacer(1, 5 * mm)]

    def para(value, column: Column):
        text = display(value, column.kind).replace('&', '&amp;').replace('<', '&lt;')
        return Paragraph(text, num_style if column.kind in ('money', 'number', 'percent') else cell_style)

    numeric = ('money', 'number', 'percent')
    data = [[Paragraph(c.label, head_num_style if c.kind in numeric else head_style) for c in result.columns]]
    data += [[para(r.get(c.key), c) for c in result.columns] for r in result.rows]
    if len(data) == 1:
        data.append([Paragraph('No records for this period.', cell_style)] + [''] * (len(result.columns) - 1))

    table = Table(data, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), brand),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F6F8F7')]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#D5DED9')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(table)

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 8 * mm, f"Generated {timezone.localtime():%d %b %Y %H:%M}")
        canvas.drawRightString(pagesize[0] - 12 * mm, 8 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()


RENDERERS = {'csv': to_csv, 'xlsx': to_xlsx, 'pdf': to_pdf, 'json': to_json}


def export(result: ReportResult, fmt: str) -> tuple[bytes, str, str]:
    """Returns (content, content_type, file extension)."""
    if fmt not in RENDERERS:
        raise ValueError(f"Unsupported format '{fmt}'. Use one of: {', '.join(RENDERERS)}")
    content_type, ext = FORMATS[fmt]
    return RENDERERS[fmt](result), content_type, ext
