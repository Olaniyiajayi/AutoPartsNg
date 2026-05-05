from enum import Enum
from typing import List, Optional

from aws_lambda_powertools.utilities.parser import BaseModel


class InvoiceStatus(str, Enum):
    """InvoiceStatus"""

    DRAFT = "DRAFT"
    SENT = "SENT"
    PAID = "PAID"
    VOID = "VOID"
    ARCHIVED = "ARCHIVED"


class InvoiceLineItem(BaseModel):
    """Invoice line item model"""

    part_id: str
    quantity: int
    unit_price: Optional[float] = None
    total: Optional[float] = None
    description: Optional[str] = None


class Invoice(BaseModel):
    """Invoice Model"""

    pk: str
    sk: str
    invoice_id: str
    tenant_id: str
    invoice_number: Optional[str] = None
    contact_id: Optional[str] = None
    invoice_status: str
    type: str = "INVOICE"
    items: List[InvoiceLineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    note: Optional[str] = None
    created_at: str
    updated_at: str


class InvoicePost(BaseModel):
    """InvoicePost Model"""

    invoice_number: Optional[str] = None
    contact_id: Optional[str] = None
    invoice_status: Optional[InvoiceStatus] = InvoiceStatus.SENT
    items: List[InvoiceLineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    note: Optional[str] = None


class InvoicePut(BaseModel):
    """InvoicePut Model"""

    invoice_id: str
    invoice_number: Optional[str] = None
    contact_id: Optional[str] = None
    invoice_status: Optional[InvoiceStatus] = InvoiceStatus.SENT
    items: List[InvoiceLineItem]
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: Optional[float] = None
    note: Optional[str] = None
