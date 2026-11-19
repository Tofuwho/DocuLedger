"""
Accounting Ledger Exporters for DocuLedger PH.
Generates QuickBooks, Xero, and BIR Summary List of Sales & Purchases (SLSP) CSVs.
"""

import csv
import io
from decimal import Decimal
from typing import List, Optional
from apps.ledger.models import InvoiceLedgerEntry


class LedgerExporter:
    """Generates standard accounting imports and statutory BIR filings."""

    @staticmethod
    def export_quickbooks_csv(entry: InvoiceLedgerEntry) -> str:
        """
        Exports a bill / journal entry formatted for QuickBooks Online / Desktop.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # QuickBooks Bill Import Header
        writer.writerow([
            "Bill No",
            "Vendor",
            "Bill Date",
            "Due Date",
            "Account",
            "Line Amount",
            "Line Description",
            "Line Tax Code",
            "PO Number",
            "Currency",
        ])

        line_items = list(entry.line_items.all())
        if not line_items:
            # Write aggregated single bill line
            writer.writerow([
                entry.invoice_number,
                entry.supplier_name,
                entry.invoice_date.strftime("%Y-%m-%d") if entry.invoice_date else "",
                entry.due_date.strftime("%Y-%m-%d") if entry.due_date else "",
                "50000 Cost of Goods Sold / Purchases",
                f"{entry.vatable_sales:.2f}",
                f"Philippine Sales Invoice {entry.invoice_number}",
                "12% Input VAT",
                entry.po_reference or "",
                entry.currency,
            ])
        else:
            for item in line_items:
                writer.writerow([
                    entry.invoice_number,
                    entry.supplier_name,
                    entry.invoice_date.strftime("%Y-%m-%d") if entry.invoice_date else "",
                    entry.due_date.strftime("%Y-%m-%d") if entry.due_date else "",
                    "50000 Cost of Goods Sold / Purchases",
                    f"{item.amount:.2f}",
                    item.description,
                    "12% Input VAT",
                    entry.po_reference or "",
                    entry.currency,
                ])

        return output.getvalue()

    @staticmethod
    def export_xero_csv(entry: InvoiceLedgerEntry) -> str:
        """
        Exports bill formatted for Xero Accounting.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "*ContactName",
            "*InvoiceNumber",
            "*InvoiceDate",
            "*DueDate",
            "Reference",
            "*Description",
            "*Quantity",
            "*UnitAmount",
            "*AccountCode",
            "*TaxType",
            "Currency",
        ])

        line_items = list(entry.line_items.all())
        if not line_items:
            writer.writerow([
                entry.supplier_name,
                entry.invoice_number,
                entry.invoice_date.strftime("%d/%m/%Y") if entry.invoice_date else "",
                entry.due_date.strftime("%d/%m/%Y") if entry.due_date else "",
                entry.po_reference or "",
                f"Sales Invoice {entry.invoice_number}",
                "1",
                f"{entry.vatable_sales:.2f}",
                "300",
                "12% VAT on Expenses",
                entry.currency,
            ])
        else:
            for item in line_items:
                writer.writerow([
                    entry.supplier_name,
                    entry.invoice_number,
                    entry.invoice_date.strftime("%d/%m/%Y") if entry.invoice_date else "",
                    entry.due_date.strftime("%d/%m/%Y") if entry.due_date else "",
                    entry.po_reference or "",
                    item.description,
                    f"{item.quantity:.2f}",
                    f"{item.unit_price:.2f}",
                    "300",
                    "12% VAT on Expenses",
                    entry.currency,
                ])

        return output.getvalue()

    @staticmethod
    def export_bir_slsp_csv(entries: List[InvoiceLedgerEntry], taxable_month: str = "2024-11") -> str:
        """
        Generates official BIR SLSP (Summary List of Sales and Purchases) - Schedule 3 (Purchases).
        Follows BIR electronic submission layout for input tax credits.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # BIR SLSP Header Row
        writer.writerow([
            "Taxable Month",
            "Taxpayer TIN",
            "Branch Code",
            "Registered Name",
            "Owner's Trade Name",
            "Address",
            "Gross Amount",
            "Exempt Amount",
            "Zero-Rated Amount",
            "Taxable Amount (Vatable)",
            "Input Tax (12% VAT)",
            "Invoice Number",
            "Invoice Date",
        ])

        for e in entries:
            # Parse TIN and branch code
            tin_digits = "".join(filter(str.isdigit, e.supplier_tin))
            base_tin = tin_digits[:9] if len(tin_digits) >= 9 else tin_digits
            branch_code = tin_digits[9:12] if len(tin_digits) >= 12 else "000"

            writer.writerow([
                taxable_month,
                base_tin,
                branch_code,
                e.supplier_name,
                e.supplier_name,
                e.supplier_address or "Philippines",
                f"{e.total_amount:.2f}",
                f"{e.vat_exempt_sales:.2f}",
                f"{e.zero_rated_sales:.2f}",
                f"{e.vatable_sales:.2f}",
                f"{e.vat_amount:.2f}",
                e.invoice_number,
                e.invoice_date.strftime("%m/%d/%Y") if e.invoice_date else "",
            ])

        return output.getvalue()
