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


class Position(str, Enum):
    """Position"""

    SALES = "SALES"
    ACCOUNTS = "ACCOUNTS"
    MANAGER = "MANAGER"


class LineItemTaxType(str, Enum):
    """LineItemTaxType"""

    EXCLUSIVE = "EXCLUSIVE"
    INCLUSIVE = "INCLUSIVE"
    NO_TAX = "NO_TAX"


class DefaultDueDate(str, Enum):
    """DefaultDueDate"""

    CASH_ON_DELIVERY = "CASH_ON_DELIVERY"
    TWENTIETH_OF_FOLLOWING_MONTH = "20TH_OF_THE_FOLLOWING_MONTH"
    TWENTIETH_OF_THIS_MONTH = "20TH_OF_THIS_MONTH"
    LAST_DAY_OF_THE_FOLLOWING_MONTH = "LAST_DAY_OF_THE_FOLLOWING_MONTH"
    SEVENTH_OF_THE_FOLLOWING_MONTH = "7TH_OF_THE_FOLLOWING_MONTH"
    SEVENTH_OF_THIS_MONTH = "7TH_OF_THIS_MONTH"

class PrimaryPerson(BaseModel):
    """PrimaryPerson model"""

    primary_person_id: str
    primary_person_first_name: Optional[str] = None
    primary_person_last_name: Optional[str] = None
    primary_person_email: Optional[str] = None
    position: Optional[Position] = None
    include_in_emails: Optional[bool] = False


class Address(BaseModel):
    """Address Model"""

    attention: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class Account(BaseModel):
    """Account"""

    account_id: str
    account_name: str


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
    is_business_contact: Optional[bool] = False
    is_capricorn_member: Optional[bool] = False
    is_on_hold: Optional[bool] = False
    on_hold_at: Optional[str] = None
    is_hidden: Optional[bool] = False
    type: str = "CONTACT"
    account_number: Optional[str] = None
    payment_type: Optional[PaymentType] = None
    primary_people: List[PrimaryPerson]
    delivery_address: Address
    same_as_delivery_address: bool
    billing_address: Address
    note: Optional[str] = None
    credit_limit: Optional[float] = None
    block_new_invoice_if_credit_exceeded: Optional[bool] = False
    line_item_tax_type: Optional[LineItemTaxType] = None
    sales_account: Optional[Account] = None
    default_due_date: Optional[str] = None
    contact_type: Optional[ContactType] = None
    created_at: str
    updated_at: str


class ContactPost(BaseModel):
    """ContactPost Model"""

    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_business_contact: Optional[bool] = False
    is_capricorn_member: Optional[bool] = False
    is_on_hold: Optional[bool] = False
    account_number: Optional[str] = None
    is_hidden: Optional[bool] = False
    payment_type: Optional[PaymentType] = None
    primary_people: List[PrimaryPerson]
    delivery_address: Address
    same_as_delivery_address: Optional[bool] = False
    billing_address: Address
    note: Optional[str] = None
    credit_limit: Optional[float] = None
    block_new_invoice_if_credit_exceeded: Optional[bool] = False
    line_item_tax_type: Optional[LineItemTaxType] = None
    sales_account: Optional[Account] = None
    default_due_date: Optional[str] = None
    contact_type: Optional[ContactType] = None


class ContactPut(BaseModel):
    """ContactPut Model"""

    contact_id: str
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    is_business_contact: Optional[bool] = False
    is_capricorn_member: Optional[bool] = False
    is_on_hold: Optional[bool] = False
    account_number: Optional[str] = None
    is_hidden: Optional[bool] = False
    payment_type: Optional[PaymentType] = None
    primary_people: List[PrimaryPerson]
    delivery_address: Address
    same_as_delivery_address: Optional[bool] = False
    billing_address: Address
    note: Optional[str] = None
    credit_limit: Optional[float] = None
    block_new_invoice_if_credit_exceeded: Optional[bool] = False
    line_item_tax_type: Optional[LineItemTaxType] = None
    sales_account: Optional[Account] = None
    default_due_date: Optional[str] = None
    contact_type: Optional[ContactType] = None


class ContactRestore(BaseModel):
    """Contact Restore Schema"""

    contact_id: str


# create the ValidateContact class
class ValidateContact(BaseModel):
    """ValidateContact model"""

    contact_name: str
    account_number: Optional[str] = None
    contact_id: Optional[str] = None


# create the ContactGetBalance class
class ContactGetBalance(BaseModel):
    """ContactGetBalance model"""

    contact_id: str


# create the ContactGetCredit class
class ContactGetCredit(BaseModel):
    """ContactGetCredit model"""

    contact_id: str

class ItemTypeEnum(str, Enum):
    """ItemType"""

    PART = "PART"
    OTHER = "OTHER"

class SalesChannelLineItem(BaseModel):
    """SalesChannelLineItem Model"""

    part_id: Optional[str] = None
    unit_price: float
    quantity: int
    item_type: ItemTypeEnum

class ContactHandleSalesChannel(BaseModel):
    """ContactHandleSalesChannel Model"""

    line_items: List[SalesChannelLineItem]
    contact_name: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_address: Address
    sales_channel: str
    reference: Optional[str] = None
    total: float
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    type: str = "CONTACT"
    contact_id: str = Field(default_factory=lambda: str(uuid4()))
    contact_status: str = "ACTIVE"


class Credentials(BaseModel):
    """Credentials model"""

    access_key: str
    secret_key: str
    token: str
    region_name: str


class ContactGetWorkOrders(BaseModel):
    """ContactGetWorkOrders"""

    contact_id: str
    page: int
    page_size: int


class ContactGetQuotes(BaseModel):
    """ContactGetWorkOrders"""

    contact_id: str
    page: int
    page_size: int


class ContactGetInvoices(BaseModel):
    """ContactGetWorkOrders"""

    contact_id: str
    page: int
    page_size: int


class ContactGetCreditNotes(BaseModel):
    """ContactGetWorkOrders"""

    contact_id: str
    page: int
    page_size: int


class ContactGetSaleMetrics(BaseModel):
    """ContactGetSaleMetrics model"""

    contact_id: str
    time_zone: str


class ContactGetTotalMetrics(BaseModel):
    """ContactGetTotalMetrics model"""

    contact_id: str


class ContactGetContacts(BaseModel):
    """ContactGetContacts model"""

    contact_ids: List[str]

# Generic table preferences models
from enum import Enum
from typing import Dict
from pydantic import StrictBool, StrictInt


class TableKeyEnum(str, Enum):
    """Supported table keys for this service."""

    CONTACT_SEARCH = "CONTACT_SEARCH"

    CONTACT_VIEW_DETAILS = "CONTACT_VIEW_DETAILS"

    CONTACT_VIEW_PRIMARY_PEOPLE = "CONTACT_VIEW_PRIMARY_PEOPLE"

    CONTACT_VIEW_TRANSACTIONS_INVOICES = "CONTACT_VIEW_TRANSACTIONS_INVOICES"

    CONTACT_VIEW_TRANSACTIONS_QUOTES = "CONTACT_VIEW_TRANSACTIONS_QUOTES"

    CONTACT_VIEW_TRANSACTIONS_CREDIT_NOTES = "CONTACT_VIEW_TRANSACTIONS_CREDIT_NOTES"

    CONTACT_VIEW_TRANSACTIONS_WORK_ORDERS = "CONTACT_VIEW_TRANSACTIONS_WORK_ORDERS"


class TableColumnConfig(BaseModel):
    """Column configuration for a single table column."""

    visible: StrictBool
    width: StrictInt
    order: StrictInt
    is_pinned: StrictBool


class TablePreferencesPayload(BaseModel):
    """Payload for table preferences updates."""

    columns: Dict[str, TableColumnConfig]


class TablePreferencesItem(BaseModel):
    """Stored table preferences item in DynamoDB."""

    pk: str
    sk: str
    tenant_id: str
    user_id: str
    table_key: TableKeyEnum
    type: str = "TABLE_CONFIG"
    table_configuration_id: str
    table_configuration: TablePreferencesPayload
    created_at: str
    updated_at: str
