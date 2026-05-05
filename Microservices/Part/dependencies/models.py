from enum import Enum
from typing import Optional

from aws_lambda_powertools.utilities.parser import BaseModel


class PartType(str, Enum):
    """PartType"""

    OEM = "OEM"
    AFTERMARKET = "AFTERMARKET"
    USED = "USED"
    REFURBISHED = "REFURBISHED"


class Part(BaseModel):
    """Part Model"""

    pk: str
    sk: str
    part_id: str
    tenant_id: str
    part_name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity_available: Optional[int] = 0
    reorder_level: Optional[int] = 0
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    part_status: str
    is_hidden: Optional[bool] = False
    type: str = "PART"
    note: Optional[str] = None
    part_type: Optional[PartType] = None
    created_at: str
    updated_at: str


class PartPost(BaseModel):
    """PartPost Model"""

    part_name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity_available: Optional[int] = 0
    reorder_level: Optional[int] = 0
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    is_hidden: Optional[bool] = False
    note: Optional[str] = None
    part_type: Optional[PartType] = None


class PartPut(BaseModel):
    """PartPut Model"""

    part_id: str
    part_name: str
    part_number: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    quantity_available: Optional[int] = 0
    reorder_level: Optional[int] = 0
    unit_price: Optional[float] = None
    cost_price: Optional[float] = None
    is_hidden: Optional[bool] = False
    note: Optional[str] = None
    part_type: Optional[PartType] = None
