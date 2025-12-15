"""
Invoice PDF Generation Service

Generates PDF invoices from invoice data using ReportLab.
PDFs are generated in-memory and returned as BytesIO buffers.
"""
from io import BytesIO
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from bson import Decimal128

from app.config import settings

logger = logging.getLogger(__name__)


def _to_float(value: Any) -> float:
    """
    Convert value to float, handling Decimal128 from MongoDB.

    Args:
        value: Value to convert (float, int, Decimal128, or str)

    Returns:
        Float value
    """
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    elif isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    else:
        return 0.0


def _format_date(date_value: Any) -> str:
    """
    Format date value as human-readable date string (e.g., "December 14, 2025").

    Args:
        date_value: datetime object or ISO string

    Returns:
        Formatted date string or 'N/A'
    """
    if isinstance(date_value, datetime):
        return date_value.strftime('%B %d, %Y')
    elif isinstance(date_value, str) and date_value != 'N/A':
        try:
            dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y')
        except ValueError:
            return date_value
    else:
        return 'N/A'


def generate_invoice_pdf(invoice_dict: Dict[str, Any], payment_link_url: Optional[str] = None) -> BytesIO:
    """
    Generate PDF invoice from invoice data.

    Args:
        invoice_dict: Invoice document from MongoDB with fields:
            - invoice_number: str
            - company_name: str
            - invoice_date: str (ISO format)
            - due_date: str (ISO format)
            - line_items: List[dict] with description, quantity, unit_price, amount
            - subtotal: float
            - tax_amount: float
            - total_amount: float

    Returns:
        BytesIO buffer containing PDF data

    Example:
        >>> invoice = {...}
        >>> pdf_buffer = generate_invoice_pdf(invoice)
        >>> pdf_bytes = pdf_buffer.getvalue()
    """
    logger.info(f"[PDF_GENERATION] Generating PDF for invoice {invoice_dict.get('invoice_number')}")

    # Create PDF buffer
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    # Container for PDF elements
    elements = []

    # Get styles
    styles = getSampleStyleSheet()

    # Company Header: Brand identity
    company_header_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2196F3'),
        alignment=TA_CENTER,
        spaceAfter=6
    )
    company_info_style = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=12
    )

    elements.append(Paragraph(settings.company_name, company_header_style))
    company_contact = f"{settings.company_email} | {settings.company_phone}"
    elements.append(Paragraph(company_contact, company_info_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Invoice Title
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#333333')
    )
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Invoice metadata section
    invoice_number = invoice_dict.get('invoice_number', 'N/A')
    company_name = invoice_dict.get('company_name', 'N/A')
    invoice_date_raw = invoice_dict.get('invoice_date', 'N/A')
    due_date_raw = invoice_dict.get('due_date', 'N/A')

    # Format dates as human-readable strings
    invoice_date = _format_date(invoice_date_raw)
    due_date = _format_date(due_date_raw)

    logger.info(f"[PDF_GENERATION] Formatted dates - Invoice: {invoice_date}, Due: {due_date}")

    metadata = [
        ['Invoice Number:', invoice_number],
        ['Bill To:', company_name],
        ['Invoice Date:', invoice_date],
        ['Due Date:', due_date]
    ]

    metadata_table = Table(metadata, colWidths=[2 * inch, 4 * inch])
    metadata_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(metadata_table)
    elements.append(Spacer(1, 0.5 * inch))

    # Line items table
    line_items = invoice_dict.get('line_items', [])

    # Table header
    table_data = [['Description', 'Quantity', 'Unit Price', 'Amount']]

    # Add line items
    for item in line_items:
        description = item.get('description', '')
        quantity = item.get('quantity', 0)
        unit_price = _to_float(item.get('unit_price', 0.0))
        amount = _to_float(item.get('amount', 0.0))

        table_data.append([
            description,
            str(quantity),
            f"${unit_price:.2f}",
            f"${amount:.2f}"
        ])

    # Create table
    items_table = Table(table_data, colWidths=[3 * inch, 1 * inch, 1.25 * inch, 1.25 * inch])
    items_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),

        # Data rows styling
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.3 * inch))

    # Summary section (subtotal, tax, total)
    subtotal = _to_float(invoice_dict.get('subtotal', 0.0))
    tax_amount = _to_float(invoice_dict.get('tax_amount', 0.0))
    total_amount = _to_float(invoice_dict.get('total_amount', 0.0))

    summary_data = [
        ['Subtotal:', f"${subtotal:.2f}"],
        ['Tax (6%):', f"${tax_amount:.2f}"],
        ['Total Amount:', f"${total_amount:.2f}"]
    ]

    summary_table = Table(summary_data, colWidths=[4.5 * inch, 1.75 * inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    elements.append(summary_table)

    # Payment Instructions section
    elements.append(Spacer(1, 0.4 * inch))

    payment_title_style = styles['Heading2']
    elements.append(Paragraph("Payment Instructions", payment_title_style))
    elements.append(Spacer(1, 0.2 * inch))

    if payment_link_url:
        # Show payment link
        payment_text = f"""
        <b>Pay Online:</b><br/>
        <link href="{payment_link_url}" color="blue">{payment_link_url}</link><br/><br/>
        Click the link above or visit the URL to pay securely via credit card, debit card, or bank account.<br/>
        <i>Powered by Stripe</i>
        """
        logger.info(f"[PDF_GENERATION] Payment link included: {payment_link_url}")
    else:
        # Fallback instructions using company settings
        payment_text = f"""
        <b>Payment Methods:</b><br/>
        Please contact our billing department for payment options:<br/><br/>
        Email: {settings.company_email}<br/>
        Phone: {settings.company_phone}
        """
        logger.warning(f"[PDF_GENERATION] No payment link available, using fallback instructions")

    payment_para = Paragraph(payment_text, styles['Normal'])
    elements.append(payment_para)

    # Build PDF
    doc.build(elements)

    # Reset buffer position to beginning
    buffer.seek(0)

    logger.info(f"[PDF_GENERATION] ✅ PDF generated successfully for {invoice_number}")

    return buffer
