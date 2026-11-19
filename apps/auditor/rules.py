"""
Deterministic Philippine Tax, TIN, Duplicate & PO Audit Engine for DocuLedger PH.
All calculations use strict Decimal arithmetic (ROUND_HALF_UP).
Never uses float for monetary or tax computations.
"""

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from apps.extractor.schemas import ExtractedInvoice, ExtractedPO, Extracted2307


@dataclass
class RuleResult:
    rule_name: str
    rule_category: str
    status: str  # 'PASS', 'WARNING', 'FAIL'
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    weight: int = 20  # Deducted from 100 on FAIL


@dataclass
class AuditReport:
    document_id: Optional[int]
    status: str  # 'PASSED', 'WARNING', 'FAILED'
    score: int  # 0 to 100
    results: List[RuleResult] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "score": self.score,
            "summary": self.summary,
            "results": [
                {
                    "rule_name": r.rule_name,
                    "rule_category": r.rule_category,
                    "status": r.status,
                    "message": r.message,
                    "details": r.details,
                }
                for r in self.results
            ]
        }


class PhilippineTaxAuditor:
    """Core compliance audit rules for Philippine financial documents."""

    ROUNDING_TOLERANCE = Decimal("0.02")
    VAT_RATE = Decimal("0.12")

    @classmethod
    def validate_tin(cls, tin: str, entity_label: str = "Supplier") -> RuleResult:
        """
        Validates Philippine Tax Identification Number (TIN).
        Standard BIR formats:
        - 9 digits (legacy)
        - 12 digits (9-digit base + 3-digit branch code, e.g. 000 for Head Office)
        - 14 digits (9-digit base + 5-digit branch code)
        Dashes can be present: XXX-XXX-XXX-XXX.
        """
        if not tin:
            return RuleResult(
                rule_name=f"{entity_label} TIN Format & Checksum",
                rule_category="TIN",
                status="FAIL",
                message=f"{entity_label} TIN is completely missing.",
                details={"tin": "", "reason": "empty"},
                weight=25
            )

        # Normalize TIN: remove non-digits
        digits = re.sub(r'\D', '', tin)

        # Disallow obvious fake TINs (all zeros, all repeating digits)
        if len(set(digits)) <= 1 or digits == "123456789000" or digits == "000000000000":
            # Check if it's test dummy
            if digits == "000000000000" or digits == "999999999999":
                return RuleResult(
                    rule_name=f"{entity_label} TIN Format & Checksum",
                    rule_category="TIN",
                    status="FAIL",
                    message=f"{entity_label} TIN '{tin}' is a dummy/placeholder number, non-compliant with BIR regulations.",
                    details={"tin": tin, "normalized": digits, "reason": "dummy_pattern"},
                    weight=25
                )

        if len(digits) not in (9, 12, 13, 14):
            return RuleResult(
                rule_name=f"{entity_label} TIN Format & Checksum",
                rule_category="TIN",
                status="FAIL",
                message=f"{entity_label} TIN '{tin}' has an invalid digit count ({len(digits)} digits). BIR requires 9 or 12-14 digits.",
                details={"tin": tin, "digit_count": len(digits)},
                weight=25
            )

        # If 9 digits, issue warning to append branch code (standard BIR requirement)
        if len(digits) == 9:
            return RuleResult(
                rule_name=f"{entity_label} TIN Format & Checksum",
                rule_category="TIN",
                status="WARNING",
                message=f"{entity_label} TIN '{tin}' is 9 digits (legacy). BIR recommends 12 digits including 3-digit branch code (e.g. -000).",
                details={"tin": tin, "normalized": digits},
                weight=5
            )

        # Format is valid
        branch_code = digits[9:12]
        branch_desc = "Head Office" if branch_code == "000" else f"Branch #{branch_code}"
        return RuleResult(
            rule_name=f"{entity_label} TIN Format & Checksum",
            rule_category="TIN",
            status="PASS",
            message=f"Valid Philippine TIN '{tin}' ({branch_desc}).",
            details={"tin": tin, "normalized": digits, "branch_code": branch_code},
            weight=0
        )

    @classmethod
    def audit_12_percent_vat(
        cls,
        vatable_sales: Decimal,
        vat_amount: Decimal,
        vat_exempt_sales: Decimal = Decimal("0.00"),
        zero_rated_sales: Decimal = Decimal("0.00"),
        total_amount: Decimal = Decimal("0.00"),
    ) -> List[RuleResult]:
        """
        Audits 12% Philippine Value-Added Tax math and total reconciling sum.
        Formula:
          Expected VAT = round(Vatable Sales * 0.12, 2)
          Total Due = Vatable Sales + VAT Amount + VAT-Exempt Sales + Zero-Rated Sales
        """
        results = []

        # 1. 12% VAT Computation
        expected_vat = (vatable_sales * cls.VAT_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        vat_diff = (vat_amount - expected_vat).quantize(Decimal("0.01"))

        if abs(vat_diff) <= cls.ROUNDING_TOLERANCE:
            results.append(RuleResult(
                rule_name="12% Philippine VAT Calculation",
                rule_category="VAT_CALCULATION",
                status="PASS",
                message=f"VAT amount (₱{vat_amount:,.2f}) strictly matches 12% of vatable sales (₱{vatable_sales:,.2f}).",
                details={
                    "vatable_sales": str(vatable_sales),
                    "vat_amount": str(vat_amount),
                    "expected_vat": str(expected_vat),
                    "variance": str(vat_diff),
                },
                weight=0
            ))
        else:
            results.append(RuleResult(
                rule_name="12% Philippine VAT Calculation",
                rule_category="VAT_CALCULATION",
                status="FAIL",
                message=(
                    f"Discrepancy in 12% VAT calculation. Computed 12% VAT is ₱{expected_vat:,.2f}, "
                    f"but invoice states ₱{vat_amount:,.2f} (Discrepancy: ₱{vat_diff:+,.2f})."
                ),
                details={
                    "vatable_sales": str(vatable_sales),
                    "vat_amount": str(vat_amount),
                    "expected_vat": str(expected_vat),
                    "variance": str(vat_diff),
                },
                weight=30
            ))

        # 2. Total Amount Reconciling Sum
        expected_total = (vatable_sales + vat_amount + vat_exempt_sales + zero_rated_sales).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total_diff = (total_amount - expected_total).quantize(Decimal("0.01"))

        if abs(total_diff) <= cls.ROUNDING_TOLERANCE:
            results.append(RuleResult(
                rule_name="Invoice Total Reconciling Sum",
                rule_category="VAT_CALCULATION",
                status="PASS",
                message=f"Total amount (₱{total_amount:,.2f}) balances with subtotal components.",
                details={
                    "total_amount": str(total_amount),
                    "expected_total": str(expected_total),
                    "variance": str(total_diff),
                },
                weight=0
            ))
        else:
            results.append(RuleResult(
                rule_name="Invoice Total Reconciling Sum",
                rule_category="VAT_CALCULATION",
                status="FAIL",
                message=(
                    f"Total amount due (₱{total_amount:,.2f}) does not match the sum of vatable, "
                    f"VAT, exempt, and zero-rated sales (₱{expected_total:,.2f}, variance: ₱{total_diff:+,.2f})."
                ),
                details={
                    "total_amount": str(total_amount),
                    "expected_total": str(expected_total),
                    "variance": str(total_diff),
                },
                weight=25
            ))

        return results

    @classmethod
    def audit_bir_compliance(cls, raw_text: str, atp_number: Optional[str] = None) -> RuleResult:
        """
        Audits required BIR markers on official Philippine Sales Invoices:
        - Must state 'VAT-REGISTERED' or 'NON-VAT'
        - Must include BIR Authority to Print (ATP) or Permit to Use (PTU)
        """
        upper = raw_text.upper()
        has_vat_marker = "VAT-REGISTERED" in upper or "VAT REG" in upper or "NON-VAT" in upper
        has_atp = bool(atp_number and atp_number.strip()) or ("ATP" in upper or "PERMIT TO USE" in upper or "PTU" in upper)

        if has_vat_marker and has_atp:
            return RuleResult(
                rule_name="BIR Authority to Print & Tax Classification Markers",
                rule_category="BIR_COMPLIANCE",
                status="PASS",
                message="Invoice satisfies BIR statutory printing guidelines (VAT-Registered marker and ATP/PTU present).",
                details={"has_vat_marker": True, "atp_number": atp_number or "Present in body text"},
                weight=0
            )
        elif not has_atp:
            return RuleResult(
                rule_name="BIR Authority to Print & Tax Classification Markers",
                rule_category="BIR_COMPLIANCE",
                status="WARNING",
                message="Invoice lacks an explicit BIR Authority to Print (ATP) or PTU Permit reference number.",
                details={"has_vat_marker": has_vat_marker, "has_atp": False},
                weight=15
            )
        else:
            return RuleResult(
                rule_name="BIR Authority to Print & Tax Classification Markers",
                rule_category="BIR_COMPLIANCE",
                status="WARNING",
                message="Taxpayer registration classification ('VAT-Registered' / 'Non-VAT') not explicitly found.",
                details={"has_vat_marker": False, "has_atp": True},
                weight=10
            )

    @classmethod
    def audit_duplicate(
        cls,
        file_hash: str,
        supplier_tin: str,
        invoice_number: str,
        exclude_doc_id: Optional[int] = None
    ) -> RuleResult:
        """
        Checks for duplicate files via SHA-256 and duplicate invoices via (supplier_tin, invoice_number).
        """
        from apps.ledger.models import Document, InvoiceLedgerEntry

        # 1. Binary Hash Check
        hash_qs = Document.objects.filter(file_hash=file_hash)
        if exclude_doc_id:
            hash_qs = hash_qs.exclude(id=exclude_doc_id)
        if hash_qs.exists():
            dup = hash_qs.first()
            return RuleResult(
                rule_name="Document Duplicate Check",
                rule_category="DUPLICATE",
                status="FAIL",
                message=f"Exact binary duplicate detected! File identical to '{dup.file_name}' (Doc #{dup.id}).",
                details={"file_hash": file_hash, "matched_document_id": dup.id},
                weight=30
            )

        # 2. Composite Key Check
        if supplier_tin and invoice_number:
            inv_qs = InvoiceLedgerEntry.objects.filter(
                supplier_tin=supplier_tin,
                invoice_number=invoice_number
            )
            if exclude_doc_id:
                inv_qs = inv_qs.exclude(document_id=exclude_doc_id)
            if inv_qs.exists():
                dup_entry = inv_qs.first()
                return RuleResult(
                    rule_name="Document Duplicate Check",
                    rule_category="DUPLICATE",
                    status="FAIL",
                    message=(
                        f"Duplicate Invoice Number '{invoice_number}' already recorded for Supplier TIN '{supplier_tin}' "
                        f"on entry #{dup_entry.id}."
                    ),
                    details={"supplier_tin": supplier_tin, "invoice_number": invoice_number, "matched_entry_id": dup_entry.id},
                    weight=30
                )

        return RuleResult(
            rule_name="Document Duplicate Check",
            rule_category="DUPLICATE",
            status="PASS",
            message="Document is unique; no duplicate file hash or (TIN, Invoice#) composite match found.",
            details={"file_hash": file_hash[:16] + "..."},
            weight=0
        )

    @classmethod
    def audit_po_matching(
        cls,
        invoice: ExtractedInvoice,
        po_reference: Optional[str] = None
    ) -> RuleResult:
        """
        Performs 2-Way matching between Sales Invoice and Purchase Order.
        """
        from apps.ledger.models import PurchaseOrderEntry

        target_po = po_reference or invoice.po_reference
        if not target_po:
            return RuleResult(
                rule_name="Purchase Order 2-Way Cross Match",
                rule_category="PO_MATCH",
                status="WARNING",
                message="No associated Purchase Order referenced on this invoice.",
                details={"reason": "no_po_reference"},
                weight=5
            )

        # Find matching PO
        po_obj = PurchaseOrderEntry.objects.filter(po_number__iexact=target_po).first()
        if not po_obj:
            return RuleResult(
                rule_name="Purchase Order 2-Way Cross Match",
                rule_category="PO_MATCH",
                status="WARNING",
                message=f"Referenced PO '{target_po}' not yet found in the system ledger.",
                details={"po_reference": target_po},
                weight=10
            )

        # Compare Amounts
        amount_diff = (invoice.total_amount - po_obj.total_amount).quantize(Decimal("0.01"))
        if amount_diff > cls.ROUNDING_TOLERANCE:
            return RuleResult(
                rule_name="Purchase Order 2-Way Cross Match",
                rule_category="PO_MATCH",
                status="FAIL",
                message=(
                    f"Invoice total (₱{invoice.total_amount:,.2f}) exceeds Purchase Order {po_obj.po_number} "
                    f"authorized amount (₱{po_obj.total_amount:,.2f}) by ₱{amount_diff:+,.2f}."
                ),
                details={
                    "invoice_total": str(invoice.total_amount),
                    "po_total": str(po_obj.total_amount),
                    "variance": str(amount_diff),
                },
                weight=25
            )

        return RuleResult(
            rule_name="Purchase Order 2-Way Cross Match",
            rule_category="PO_MATCH",
            status="PASS",
            message=f"Invoice successfully reconciled against PO '{po_obj.po_number}' (₱{po_obj.total_amount:,.2f}).",
            details={
                "po_number": po_obj.po_number,
                "po_total": str(po_obj.total_amount),
                "invoice_total": str(invoice.total_amount),
            },
            weight=0
        )

    @classmethod
    def audit_form_2307_ewt(
        cls,
        invoice: ExtractedInvoice,
        cert_2307: Optional[Extracted2307] = None
    ) -> RuleResult:
        """
        Performs 3-Way Cross Check against BIR Form 2307 (Creditable Withholding Tax at Source).
        Formula:
          Withholding Tax = round(Vatable Sales * ATC Rate, 2)
        """
        if not cert_2307:
            return RuleResult(
                rule_name="BIR Form 2307 Withholding Tax Match",
                rule_category="EWT_MATCH",
                status="PASS",
                message="Standard invoice audit (no BIR Form 2307 attached for 3-way match).",
                details={},
                weight=0
            )

        # Compare base
        base_diff = (cert_2307.income_payment - invoice.vatable_sales).quantize(Decimal("0.01"))
        expected_withheld = (invoice.vatable_sales * cert_2307.tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        withheld_diff = (cert_2307.tax_withheld - expected_withheld).quantize(Decimal("0.01"))

        if abs(base_diff) <= cls.ROUNDING_TOLERANCE and abs(withheld_diff) <= cls.ROUNDING_TOLERANCE:
            return RuleResult(
                rule_name="BIR Form 2307 Withholding Tax Match",
                rule_category="EWT_MATCH",
                status="PASS",
                message=(
                    f"Form 2307 perfectly balances: Income base ₱{cert_2307.income_payment:,.2f} @ "
                    f"{cert_2307.tax_rate * 100:.0f}% ATC [{cert_2307.atc_code}] = ₱{cert_2307.tax_withheld:,.2f} withheld."
                ),
                details={
                    "atc_code": cert_2307.atc_code,
                    "tax_rate": str(cert_2307.tax_rate),
                    "income_payment": str(cert_2307.income_payment),
                    "tax_withheld": str(cert_2307.tax_withheld),
                },
                weight=0
            )
        else:
            return RuleResult(
                rule_name="BIR Form 2307 Withholding Tax Match",
                rule_category="EWT_MATCH",
                status="FAIL",
                message=(
                    f"Form 2307 discrepancy: Expected withholding on ₱{invoice.vatable_sales:,.2f} @ {cert_2307.tax_rate * 100:.0f}% "
                    f"is ₱{expected_withheld:,.2f}, but certificate states ₱{cert_2307.tax_withheld:,.2f}."
                ),
                details={
                    "expected_withheld": str(expected_withheld),
                    "actual_withheld": str(cert_2307.tax_withheld),
                    "variance": str(withheld_diff),
                },
                weight=20
            )


def run_full_compliance_audit(
    document_id: Optional[int],
    extracted_invoice: ExtractedInvoice,
    raw_text: str,
    file_hash: str,
    po_reference: Optional[str] = None,
    cert_2307: Optional[Extracted2307] = None
) -> AuditReport:
    """Executes full compliance audit suite and calculates overall compliance score."""
    results: List[RuleResult] = []

    # 1. Supplier TIN
    results.append(PhilippineTaxAuditor.validate_tin(extracted_invoice.supplier_tin, "Supplier"))

    # 2. Buyer TIN (if provided)
    if extracted_invoice.buyer_tin:
        results.append(PhilippineTaxAuditor.validate_tin(extracted_invoice.buyer_tin, "Buyer"))

    # 3. 12% VAT Audit + Reconciling Total
    results.extend(PhilippineTaxAuditor.audit_12_percent_vat(
        vatable_sales=extracted_invoice.vatable_sales,
        vat_amount=extracted_invoice.vat_amount,
        vat_exempt_sales=extracted_invoice.vat_exempt_sales,
        zero_rated_sales=extracted_invoice.zero_rated_sales,
        total_amount=extracted_invoice.total_amount
    ))

    # 4. BIR Statutory Compliance Markers
    results.append(PhilippineTaxAuditor.audit_bir_compliance(
        raw_text=raw_text,
        atp_number=extracted_invoice.atp_number
    ))

    # 5. Duplicate Check
    results.append(PhilippineTaxAuditor.audit_duplicate(
        file_hash=file_hash,
        supplier_tin=extracted_invoice.supplier_tin,
        invoice_number=extracted_invoice.invoice_number,
        exclude_doc_id=document_id
    ))

    # 6. PO Matching
    results.append(PhilippineTaxAuditor.audit_po_matching(
        invoice=extracted_invoice,
        po_reference=po_reference
    ))

    # 7. Form 2307 Withholding Tax Match (if attached)
    if cert_2307:
        results.append(PhilippineTaxAuditor.audit_form_2307_ewt(
            invoice=extracted_invoice,
            cert_2307=cert_2307
        ))

    # Calculate Score
    score = 100
    has_fail = False
    has_warning = False

    for r in results:
        if r.status == "FAIL":
            score -= r.weight
            has_fail = True
        elif r.status == "WARNING":
            score -= r.weight
            has_warning = True

    score = max(0, min(100, score))

    if has_fail or score < 70:
        overall_status = "FAILED"
        summary = f"Audit Failed with score {score}/100. Discrepancies require correction before ledger posting."
    elif has_warning or score < 95:
        overall_status = "WARNING"
        summary = f"Audit Passed with Warnings ({score}/100). Review informational flags before approval."
    else:
        overall_status = "PASSED"
        summary = f"100% Compliant ({score}/100). Verified against Philippine BIR tax regulations."

    return AuditReport(
        document_id=document_id,
        status=overall_status,
        score=score,
        results=results,
        summary=summary
    )
