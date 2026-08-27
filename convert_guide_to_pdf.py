"""
convert_guide_to_pdf.py
Converts COMPREHENSIVE_SYSTEM_GUIDE.md into a high-quality, formatted PDF manual using ReportLab.
"""

import os
import sys
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# ── Color Palette ──────────────────────────────────────────────────
PRIMARY_DARK = colors.HexColor("#0D1117")   # Deep navy/black
PRIMARY_ACCENT = colors.HexColor("#0284C7") # Ocean Blue
SECONDARY_ACCENT = colors.HexColor("#7E22CE") # Deep Purple
GREEN_ACCENT = colors.HexColor("#10B981")   # Emerald Green
ORANGE_ACCENT = colors.HexColor("#F59E0B")  # Amber
RED_ACCENT = colors.HexColor("#EF4444")     # Crimson
TEXT_DARK = colors.HexColor("#1E293B")      # Charcoal body text
TEXT_MUTED = colors.HexColor("#64748B")     # Muted grey
BG_CARD = colors.HexColor("#F8FAFC")        # Soft grey card background
BG_CODE = colors.HexColor("#0F172A")        # Dark code box
BORDER_COLOR = colors.HexColor("#E2E8F0")   # Border grey

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to add running headers and 'Page X of Y' footers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # Suppress header/footer on title page
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(TEXT_MUTED)

        # Header
        self.drawString(54, 750, "CTG-CPM: SELF-HEALING NETWORKS MASTER TECHNICAL MANUAL")
        self.setStrokeColor(BORDER_COLOR)
        self.setLineWidth(0.5)
        self.line(54, 742, 558, 742)

        # Footer
        self.line(54, 45, 558, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "CONFIDENTIAL  •  VIT UNIVERISTY  •  2026")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_pdf(md_path, pdf_path):
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Paragraph Styles
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=PRIMARY_DARK,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=PRIMARY_ACCENT,
        spaceAfter=15
    ))

    styles.add(ParagraphStyle(
        'SectionHeading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=PRIMARY_DARK,
        spaceBefore=18,
        spaceAfter=8,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'SectionHeading2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=PRIMARY_ACCENT,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=TEXT_DARK,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=TEXT_DARK,
        spaceAfter=4,
        leftIndent=15
    ))

    styles.add(ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#A7F3D0"),
        spaceAfter=0
    ))

    styles.add(ParagraphStyle(
        'QAQuestion',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=PRIMARY_DARK,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'QAAnswer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=TEXT_DARK,
        spaceAfter=8,
        leftIndent=12
    ))

    story = []

    # Read markdown file
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Title Banner Block
    story.append(Spacer(1, 10))
    story.append(Paragraph("CTG-CPM: MASTER TECHNICAL MANUAL", styles['DocTitle']))
    story.append(Paragraph("Self-Healing Networks & Host Predictive Maintenance via Counterfactual Telemetry", styles['DocSubtitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY_ACCENT, spaceBefore=0, spaceAfter=15))

    # Info Card Table
    meta_data = [
        [
            Paragraph("<b>Project:</b> CTG-CPM Self-Healing System", styles['CustomBody']),
            Paragraph("<b>Version:</b> 2.0 (LLM Integrated)", styles['CustomBody'])
        ],
        [
            Paragraph("<b>Authors:</b> Sagnik Basu, C Sriharsha, Maitree Singh", styles['CustomBody']),
            Paragraph("<b>Target MTTR:</b> &lt; 10 Seconds", styles['CustomBody'])
        ]
    ]
    t_meta = Table(meta_data, colWidths=[250, 250])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG_CARD),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 15))

    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []

    def clean_text(t):
        t = t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', t)
        t = re.sub(r'\*(.*?)\*', r'<i>\1</i>', t)
        t = re.sub(r'`(.*?)`', r'<font face="Courier" color="#0284C7">\1</font>', t)
        return t

    for line in lines:
        raw_line = line
        line_str = line.strip()

        # Code block toggle
        if line_str.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "<br/>".join([c.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;') for c in code_lines])
                code_p = Paragraph(code_text, styles['CodeStyle'])
                t_code = Table([[code_p]], colWidths=[500])
                t_code.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), BG_CODE),
                    ('BOX', (0, 0), (-1, -1), 1, PRIMARY_DARK),
                    ('PADDING', (0, 0), (-1, -1), 10),
                ]))
                story.append(Spacer(1, 4))
                story.append(t_code)
                story.append(Spacer(1, 8))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(raw_line.rstrip())
            continue

        # Markdown Table parsing
        if line_str.startswith("|") and "|" in line_str[1:]:
            if "---" in line_str:
                continue # Skip table delimiter line
            cells = [clean_text(c.strip()) for c in line_str.split("|")[1:-1]]
            if cells:
                table_rows.append(cells)
                in_table = True
            continue
        elif in_table:
            # End of table
            in_table = False
            if table_rows:
                # Build reportlab table
                formatted_rows = []
                for r_idx, row in enumerate(table_rows):
                    f_row = []
                    for c in row:
                        style = styles['QAQuestion'] if r_idx == 0 else styles['CustomBody']
                        f_row.append(Paragraph(c, style))
                    formatted_rows.append(f_row)

                # Determine col widths dynamically
                col_cnt = len(table_rows[0])
                col_w = 500 / max(col_cnt, 1)
                tbl = Table(formatted_rows, colWidths=[col_w] * col_cnt)
                tbl.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), BG_CARD),
                    ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                story.append(Spacer(1, 6))
                story.append(tbl)
                story.append(Spacer(1, 10))
                table_rows = []

        if not line_str:
            story.append(Spacer(1, 4))
            continue

        # Headings
        if line_str.startswith("# "):
            # Major Section Heading
            h_text = clean_text(line_str[2:])
            story.append(Spacer(1, 12))
            story.append(Paragraph(h_text, styles['SectionHeading1']))
            story.append(HRFlowable(width="100%", thickness=1, color=PRIMARY_ACCENT, spaceBefore=2, spaceAfter=8))
        elif line_str.startswith("## "):
            h_text = clean_text(line_str[3:])
            story.append(Spacer(1, 10))
            story.append(Paragraph(h_text, styles['SectionHeading1']))
        elif line_str.startswith("### "):
            h_text = clean_text(line_str[4:])
            if h_text.startswith("Q"):
                story.append(Paragraph(h_text, styles['QAQuestion']))
            else:
                story.append(Paragraph(h_text, styles['SectionHeading2']))
        elif line_str.startswith("> "):
            # Q&A Blockquote or Callout
            quote_text = clean_text(line_str[2:])
            story.append(Paragraph(quote_text, styles['QAAnswer']))
        elif line_str.startswith("- ") or line_str.startswith("* "):
            b_text = clean_text(line_str[2:])
            story.append(Paragraph(f"• {b_text}", styles['BulletText']))
        elif re.match(r'^\d+\.\s', line_str):
            b_text = clean_text(re.sub(r'^\d+\.\s', '', line_str))
            story.append(Paragraph(f"• {b_text}", styles['BulletText']))
        else:
            p_text = clean_text(line_str)
            story.append(Paragraph(p_text, styles['CustomBody']))

    # Flush remaining table if file ends with table
    if table_rows:
        formatted_rows = []
        for r_idx, row in enumerate(table_rows):
            f_row = []
            for c in row:
                style = styles['QAQuestion'] if r_idx == 0 else styles['CustomBody']
                f_row.append(Paragraph(c, style))
            formatted_rows.append(f_row)
        col_cnt = len(table_rows[0])
        col_w = 500 / max(col_cnt, 1)
        tbl = Table(formatted_rows, colWidths=[col_w] * col_cnt)
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BG_CARD),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(Spacer(1, 6))
        story.append(tbl)

    # Build document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully built: {pdf_path}")

if __name__ == "__main__":
    md_file = r"d:\Predictive Maintenance Project 3\COMPREHENSIVE_SYSTEM_GUIDE.md"
    pdf_file = r"d:\Predictive Maintenance Project 3\COMPREHENSIVE_SYSTEM_GUIDE.pdf"
    build_pdf(md_file, pdf_file)
