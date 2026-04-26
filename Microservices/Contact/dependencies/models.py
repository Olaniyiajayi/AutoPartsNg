from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4
from enum import Enum
from aws_lambda_powertools.utilities.parser import BaseModel, Field


class PaymentType(str, Enum):
    """PaymentType"""

    ACCOUNT = "ACCOUNT"
    CASH = "CASH"
    CAPRICORN = "CAPRICORN"


class ContactType(str, Enum):
    """ContactType"""

    CUSTOMER = "CUSTOMER"
    SUPPLIER = "SUPPLIER"
    BOTH = "BOTH"


class Address(BaseModel):
    """Address Model"""

    attention: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class Contact(BaseModel):
    """Contact Model"""

    pk: str
    sk: str
    contact_id: str
    tenant_id: str
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_status: str
    is_hidden: Optional[bool] = False
    type: str = "CONTACT"
    account_number: Optional[str] = None
    payment_type: Optional[PaymentType] = None
    delivery_address: Address
    same_as_delivery_address: bool
    billing_address: Address
    note: Optional[str] = None
    contact_type: Optional[ContactType] = None
    created_at: str
    updated_at: str


class ContactPost(BaseModel):
    """ContactPost Model"""

    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    account_number: Optional[str] = None
    is_hidden: Optional[bool] = False
    payment_type: Optional[PaymentType] = None
    delivery_address: Address
    same_as_delivery_address: Optional[bool] = False
    billing_address: Address
    note: Optional[str] = None
    contact_type: Optional[ContactType] = None


class ContactPut(BaseModel):
    """ContactPut Model"""

    contact_id: str
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    account_number: Optional[str] = None
    is_hidden: Optional[bool] = False
    payment_type: Optional[PaymentType] = None
    delivery_address: Address
    same_as_delivery_address: Optional[bool] = False
    billing_address: Address
    note: Optional[str] = None
    contact_type: Optional[ContactType] = None
