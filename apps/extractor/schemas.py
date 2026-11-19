"""
Pydantic v2 extraction and bounding-box schemas for DocuLedger PH.
Enforces strict monetary types (Decimal) and coordinate structures.
"""

from decimal import Decimal
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator


class BoundingBox(BaseModel):
    """Normalized or point coordinate box on a PDF page."""
    page: int = Field(default=0, description="0-indexed page number")
    x0: float = Field(..., description="Left coordinate")
    y0: float = Field(..., description="Top coordinate")
    x1: float = Field(..., description="Right coordinate")
    y1: float = Field(..., description="Bottom coordinate")
    
    def as_rect(self) -> List[float]:
        return [self.x0, self.y0, self.x1, self.y1]


class ExtractedLineItem(BaseModel):
    """Single line item from invoice or PO."""
    item_code: Optional[str] = Field(default="", description="Product or service code")
    description: str = Field(..., description="Item or service description")
    quantity: Decimal = Field(default=Decimal("1.00"), description="Quantity")
    unit_price: Decimal = Field(default=Decimal("0.00"), description="Unit price in PHP")
    amount: Decimal = Field(default=Decimal("0.00"), description="Total line amount")
    bbox: Optional[BoundingBox] = None

    @field_validator("quantity", "unit_price", "amount", mode="before")
    @classmethod
    def parse_decimal(cls, v: Any) -> Decimal:
        if v is None:
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            # Strip currency symbols and commas
            clean = str(v).replace("PHP", "").replace("Php", "").replace("₱", "").replace(",", "").strip()
            if not clean:
                return Decimal("0.00")
            return Decimal(clean).quantize(Decimal("0.01"))
        return v


class ExtractedInvoice(BaseModel):
    """Schema for Philippine Sales Invoice extraction."""
    invoice_number: str = Field(..., description="Sales Invoice number / SI No.")
    invoice_date: Optional[str] = Field(default=None, description="Invoice issue date (YYYY-MM-DD)")
    due_date: Optional[str] = Field(default=None, description="Due date (YYYY-MM-DD)")
    
    supplier_name: str = Field(..., description="Registered Business Name of Supplier")
    supplier_tin: str = Field(..., description="Supplier Tax Identification Number (e.g. 123-456-789-000)")
    supplier_address: Optional[str] = Field(default="", description="Supplier registered address")
    
    buyer_name: str = Field(..., description="Buyer or Customer Name")
    buyer_tin: Optional[str] = Field(default="", description="Buyer Tax Identification Number")
    
    vatable_sales: Decimal = Field(default=Decimal("0.00"), description="Vatable Sales Base")
    vat_amount: Decimal = Field(default=Decimal("0.00"), description="12% Value-Added Tax")
    vat_exempt_sales: Decimal = Field(default=Decimal("0.00"), description="VAT-Exempt Sales")
    zero_rated_sales: Decimal = Field(default=Decimal("0.00"), description="Zero-Rated Sales")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Total Amount Due")
    
    atp_number: Optional[str] = Field(default="", description="BIR Authority to Print / PTU / CAS No.")
    po_reference: Optional[str] = Field(default="", description="Purchase Order reference number")
    
    line_items: List[ExtractedLineItem] = Field(default_factory=list)
    bounding_boxes: Dict[str, BoundingBox] = Field(default_factory=dict)

    @field_validator("vatable_sales", "vat_amount", "vat_exempt_sales", "zero_rated_sales", "total_amount", mode="before")
    @classmethod
    def parse_money(cls, v: Any) -> Decimal:
        if v is None:
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            clean = str(v).replace("PHP", "").replace("Php", "").replace("₱", "").replace(",", "").strip()
            if not clean:
                return Decimal("0.00")
            return Decimal(clean).quantize(Decimal("0.01"))
        return v


class ExtractedPO(BaseModel):
    """Schema for Philippine Purchase Order extraction."""
    po_number: str = Field(..., description="Purchase Order Number")
    po_date: Optional[str] = Field(default=None, description="PO Date (YYYY-MM-DD)")
    vendor_name: str = Field(..., description="Supplier / Vendor Name")
    vendor_tin: Optional[str] = Field(default="", description="Vendor TIN")
    buyer_name: str = Field(..., description="Company Issuing the PO")
    total_amount: Decimal = Field(default=Decimal("0.00"), description="Total PO Amount")
    line_items: List[ExtractedLineItem] = Field(default_factory=list)
    bounding_boxes: Dict[str, BoundingBox] = Field(default_factory=dict)

    @field_validator("total_amount", mode="before")
    @classmethod
    def parse_money(cls, v: Any) -> Decimal:
        if v is None:
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            clean = str(v).replace("PHP", "").replace("Php", "").replace("₱", "").replace(",", "").strip()
            if not clean:
                return Decimal("0.00")
            return Decimal(clean).quantize(Decimal("0.01"))
        return v


class Extracted2307(BaseModel):
    """Schema for BIR Form 2307 Creditable Withholding Tax certificate."""
    payor_name: str = Field(..., description="Payor / Withholding Agent Name")
    payor_tin: str = Field(..., description="Payor TIN")
    payee_name: str = Field(..., description="Payee / Recipient Name")
    payee_tin: str = Field(..., description="Payee TIN")
    period_from: Optional[str] = Field(default=None)
    period_to: Optional[str] = Field(default=None)
    atc_code: str = Field(default="WC158", description="Alphanumeric Tax Code (e.g. WC158 for 1%, WI158 for 2%)")
    income_payment: Decimal = Field(default=Decimal("0.00"), description="Gross Income Payment")
    tax_rate: Decimal = Field(default=Decimal("0.01"), description="Tax Rate (0.01 = 1%, 0.02 = 2%)")
    tax_withheld: Decimal = Field(default=Decimal("0.00"), description="Amount of Tax Withheld")
    bounding_boxes: Dict[str, BoundingBox] = Field(default_factory=dict)

    @field_validator("income_payment", "tax_rate", "tax_withheld", mode="before")
    @classmethod
    def parse_money(cls, v: Any) -> Decimal:
        if v is None:
            return Decimal("0.00")
        if isinstance(v, (int, float, str)):
            clean = str(v).replace("PHP", "").replace("Php", "").replace("₱", "").replace("%", "").replace(",", "").strip()
            if not clean:
                return Decimal("0.00")
            return Decimal(clean).quantize(Decimal("0.01"))
        return v


class DocumentExtractionResult(BaseModel):
    """Consolidated result returned by the extractor tier."""
    document_type: str = Field(..., description="SALES_INVOICE, PURCHASE_ORDER, or BIR_2307")
    data: Union[ExtractedInvoice, ExtractedPO, Extracted2307]
    raw_text: str = Field(default="")
    page_count: int = Field(default=1)
    bounding_boxes: Dict[str, Any] = Field(default_factory=dict)
