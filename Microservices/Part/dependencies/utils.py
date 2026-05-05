"""
Part utils for the part service
"""

# Standard library imports
from decimal import Decimal
from json import JSONEncoder, dumps
from time import time
from typing import Any, Optional
from uuid import uuid4
from datetime import datetime, timezone
from os import environ, getenv
from boto3 import client, resource

# Third party imports
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from aws_lambda_powertools.utilities import parameters
from algoliasearch.search_client import SearchClient


# Logger
logger = Logger()

# environment variables
EVENT_BUS_NAME = environ["EventBusName"]

# eventbridge client
eventbridge = client("events")
dynamodb = resource("dynamodb")
table_name = getenv("TableName")
table = dynamodb.Table(table_name)

class DecimalEncoder(JSONEncoder):
    """Handle decimal encoding

    Returns:
        Decimal: The decimal value
    """

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def generate_xray_trace_header() -> str:
    """Generate an X-Ray trace header

    Returns:
        str: The X-Ray trace header
    """
    logger.info("INSIDE GENERATE XRAY TRACE HEADER FUNCTION")
    # Generate root trace ID
    epoch = int(time())
    unique_id = uuid4().hex[:24]
    root = f"1-{epoch:08x}-{unique_id}"

    # Generate parent span ID
    parent = uuid4().hex[:16]

    # Combine into trace header
    trace_header = f"Root=PartService;{root};Parent={parent};Sampled=1"

    return trace_header


def send_event(
    tenant_id: str,
    user_id: str,
    object_id: str,
    body: dict,
    detail_type: str,
) -> None:
    """
    Send an event to EventBridge.

    Args:
        tenant_id (str): The tenant ID
        user_id (str): The user ID
        object_id (str): The object ID
        body (dict): The body of the event
        detail_type (str): The detail type of the event
    Returns:
        None
    """
    logger.info("INSIDE SEND EVENT FUNCTION")
    # Send the event to EventBridge
    event = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "id": object_id,
        "body": body,
    }
    logger.info("Sending event to EventBridge: %s", event)
    event_str = dumps(event, cls=DecimalEncoder)
    event_bridge_response = eventbridge.put_events(
        Entries=[
            {
                "Source": "PART",
                "DetailType": detail_type,
                "Detail": event_str,
                "TraceHeader": generate_xray_trace_header(),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )
    logger.info("EventBridge: %s", event_bridge_response)


# validate the input payload
def validate_payload(event: dict, model: Any) -> dict:
    """
    Validate the input payload against a given model.

    Args:
        event (dict): The input payload to be validated
        model (class): The model to validate the payload against

    Returns:
        dict: The parsed and validated payload

    Raises:
        ValueError: If the payload is invalid
    """
    logger.info("INSIDE VALIDATE PAYLOAD FUNCTION")
    try:
        logger.info(f"Payload to validate: {event}")
        return parse(event=event, model=model)
    except ValidationError as e:
        raise ValueError(e) from e


def get_detail_body(event: dict) -> dict:
    """Extract the body emitted by service send_event helpers."""
    detail = event.get("detail", {})
    return detail.get("body", detail)


def quantity_by_part(items: list) -> dict:
    """Aggregate invoice quantities by part_id."""
    quantities = {}
    for item in items or []:
        part_id = item.get("part_id")
        quantity = item.get("quantity", 0)
        if not part_id:
            continue
        quantities[part_id] = quantities.get(part_id, 0) + int(quantity)
    return quantities


def apply_quantity_delta(tenant_id: str, part_id: str, delta: int) -> dict:
    """Add a signed delta to a part's available quantity."""
    if delta == 0:
        logger.info("Skipping zero quantity delta for part %s", part_id)
        return {}

    logger.info("Applying quantity delta %s to part %s", delta, part_id)
    result = table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"},
        UpdateExpression="SET updated_at = :updated_at ADD quantity_available :delta",
        ExpressionAttributeValues={
            ":updated_at": datetime.now(timezone.utc).isoformat(),
            ":delta": Decimal(delta),
        },
        ConditionExpression="attribute_exists(pk) AND attribute_exists(sk)",
        ReturnValues="ALL_NEW",
    )
    return result.get("Attributes")


def apply_invoice_items(tenant_id: str, items: list, sign: int) -> None:
    """Apply all invoice item quantities using sign -1 for sold, +1 for restored."""
    for part_id, quantity in quantity_by_part(items).items():
        apply_quantity_delta(tenant_id, part_id, sign * quantity)


def apply_invoice_update(tenant_id: str, old_items: list, new_items: list) -> None:
    """Apply the inventory delta between old and new invoice items."""
    old_quantities = quantity_by_part(old_items)
    new_quantities = quantity_by_part(new_items)
    part_ids = set(old_quantities) | set(new_quantities)

    for part_id in part_ids:
        delta = old_quantities.get(part_id, 0) - new_quantities.get(part_id, 0)
        apply_quantity_delta(tenant_id, part_id, delta)


def get_algolia_index():
    """Get or initialize Algolia index for part uniqueness checks."""
    stage = getenv("Stage")
    algolia_app_id = parameters.get_parameter(f"/{stage}/algolia/ALGOLIA_APP_ID")
    algolia_api_key = parameters.get_parameter(f"/{stage}/algolia/ALGOLIA_API_KEY")
    index_name = getenv("ALG_PART_INDEX_NAME", "parts-v5")
    
    algolia_client = SearchClient.create(algolia_app_id, algolia_api_key)
    return algolia_client.init_index(index_name)


def is_part_name_unique_algolia(
    tenant_id: str, part_name: str, exclude_part_id: str = None
) -> bool:
    """
    Check if the part name is unique among active parts using Algolia.
    This performs a case-insensitive check.
    
    Args:
        tenant_id: The tenant ID
        part_name: The part name to check
        exclude_part_id: Optional part ID to exclude from the check (for updates)
    
    Returns:
        bool: True if unique, False if a case-insensitive match exists with different casing
    """
    try:
        index = get_algolia_index()
        normalized_name = part_name.strip().lower()
        part_name_trimmed = part_name.strip()
        
        # Build filters
        filters = [f"tenant_id:{tenant_id}"]
        
        # Exclude the current part if updating
        if exclude_part_id:
            filters.append(f"NOT objectID:{exclude_part_id}")
        
        # Use Algolia's search with the part name as query
        # Algolia's default text search is case-insensitive, so this will find matches
        # regardless of case. We then verify exact matches in Python.
        search_params = {
            "filters": " AND ".join(filters),
            "hitsPerPage": 50,  # Get enough results to check for case-insensitive matches
            "attributesToRetrieve": ["part_name", "objectID"],
            "getRankingInfo": False,
        }
        
        # Search using the part name - Algolia will find case-insensitive matches
        results = index.search(part_name_trimmed, search_params)
        hits = results.get("hits", [])
        
        # Check each hit for case-insensitive match
        # We need to verify that the normalized names match exactly
        for hit in hits:
            stored_part_name = hit.get("part_name", "")
            if not stored_part_name:
                continue
                
            stored_normalized = stored_part_name.strip().lower()
            
            # Case-insensitive match found
            if stored_normalized == normalized_name:
                # If we're updating (exclude_part_id provided), exact case match means it's the same part (allowed)
                # If we're creating (exclude_part_id is None), any case-insensitive match should be rejected
                if exclude_part_id and stored_part_name == part_name_trimmed:
                    # This is the same part being updated with same name - allowed
                    continue
                else:
                    # Case-insensitive match found - not unique
                    logger.info(
                        f"Part name '{part_name}' conflicts with existing part "
                        f"'{stored_part_name}' (case-insensitive match)"
                    )
                    return False
        
        # No conflicts found
        return True
        
    except Exception as error:
        logger.error(f"Error checking part name uniqueness in Algolia: {error}")
        # Fallback: return True to allow the operation if Algolia fails
        # This prevents blocking operations if Algolia is temporarily unavailable
        # The DynamoDB sync will eventually catch any duplicates
        logger.warning("Falling back to allowing operation due to Algolia error")
        return True


def is_part_number_unique_algolia(
    tenant_id: str, part_number: str, exclude_part_id: str = None
) -> bool:
    """
    Check if the part number is unique among active parts using Algolia.
    
    Args:
        tenant_id: The tenant ID
        part_number: The part number to check
        exclude_part_id: Optional part ID to exclude from the check (for updates)
    
    Returns:
        bool: True if unique, False if a match exists
    """
    try:
        index = get_algolia_index()
        if not part_number:
            return True
        
        # Build filters
        filters = [f"tenant_id:{tenant_id}"]
        
        # Exclude the current part if updating
        if exclude_part_id:
            filters.append(f"NOT objectID:{exclude_part_id}")
        
        # Search with part_number as query and filters
        # We'll verify exact matches in Python since Algolia text search might be fuzzy
        search_params = {
            "filters": " AND ".join(filters),
            "hitsPerPage": 10,  # Get enough to check for exact matches
            "attributesToRetrieve": ["part_number", "objectID"],
        }
        
        results = index.search(part_number, search_params)
        hits = results.get("hits", [])
        
        # Check each hit for exact part_number match
        for hit in hits:
            stored_part_number = hit.get("part_number")
            if stored_part_number == part_number:
                logger.info(f"Part number '{part_number}' is not unique")
                return False
        
        logger.info(f"Part number '{part_number}' is unique")
        return True
        
    except Exception as error:
        logger.error(f"Error checking part number uniqueness in Algolia: {error}")
        # Fallback: return True to allow the operation if Algolia fails
        # This prevents blocking operations if Algolia is temporarily unavailable
        # The DynamoDB sync will eventually catch any duplicates
        logger.warning("Falling back to allowing operation due to Algolia error")
        return True
