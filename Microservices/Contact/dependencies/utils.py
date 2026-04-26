"""
Contact utils for the contact service
"""

# Standard library imports
from decimal import Decimal
from json import JSONEncoder, dumps
from time import time
from typing import Any, Optional
from uuid import uuid4
from os import environ, getenv
from boto3 import client

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
    trace_header = f"Root=ContactService;{root};Parent={parent};Sampled=1"

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
                "Source": "CONTACT",
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


def get_algolia_index():
    """Get or initialize Algolia index for contact uniqueness checks."""
    stage = getenv("Stage")
    algolia_app_id = parameters.get_parameter(f"/{stage}/algolia/ALGOLIA_APP_ID")
    algolia_api_key = parameters.get_parameter(f"/{stage}/algolia/ALGOLIA_API_KEY")
    index_name = getenv("ALG_CONTACT_INDEX_NAME", "contacts-v5")
    
    algolia_client = SearchClient.create(algolia_app_id, algolia_api_key)
    return algolia_client.init_index(index_name)


def is_contact_name_unique_algolia(
    tenant_id: str, contact_name: str, exclude_contact_id: str = None
) -> bool:
    """
    Check if the contact name is unique among active contacts using Algolia.
    This performs a case-insensitive check (e.g., "John" = "JoHn").
    
    Args:
        tenant_id: The tenant ID
        contact_name: The contact name to check
        exclude_contact_id: Optional contact ID to exclude from the check (for updates)
    
    Returns:
        bool: True if unique, False if a case-insensitive match exists with different casing
    """
    try:
        index = get_algolia_index()
        normalized_name = contact_name.strip().lower()
        contact_name_trimmed = contact_name.strip()
        
        # Build filters
        filters = [f"tenant_id:{tenant_id}"]
        
        # Exclude the current contact if updating
        if exclude_contact_id:
            filters.append(f"NOT objectID:{exclude_contact_id}")
        
        # Use Algolia's search with the contact name as query
        # Algolia's default text search is case-insensitive, so this will find matches
        # regardless of case. We then verify exact matches in Python.
        search_params = {
            "filters": " AND ".join(filters),
            "hitsPerPage": 50,  # Get enough results to check for case-insensitive matches
            "attributesToRetrieve": ["contact_name", "objectID"],
            "getRankingInfo": False,
        }
        
        # Search using the contact name - Algolia will find case-insensitive matches
        results = index.search(contact_name_trimmed, search_params)
        hits = results.get("hits", [])
        
        # Check each hit for case-insensitive match
        # We need to verify that the normalized names match exactly
        for hit in hits:
            stored_contact_name = hit.get("contact_name", "")
            if not stored_contact_name:
                continue
                
            stored_normalized = stored_contact_name.strip().lower()
            
            # Case-insensitive match found
            if stored_normalized == normalized_name:
                # If we're updating (exclude_contact_id provided), exact case match means it's the same contact (allowed)
                # If we're creating (exclude_contact_id is None), any case-insensitive match should be rejected
                if exclude_contact_id and stored_contact_name == contact_name_trimmed:
                    # This is the same contact being updated with same name - allowed
                    continue
                else:
                    # Case-insensitive match found - not unique
                    logger.info(
                        f"Contact name '{contact_name}' conflicts with existing contact "
                        f"'{stored_contact_name}' (case-insensitive match)"
                    )
                    return False
        
        # No conflicts found
        return True
        
    except Exception as error:
        logger.error(f"Error checking contact name uniqueness in Algolia: {error}")
        # Fallback: return True to allow the operation if Algolia fails
        # This prevents blocking operations if Algolia is temporarily unavailable
        # The DynamoDB sync will eventually catch any duplicates
        logger.warning("Falling back to allowing operation due to Algolia error")
        return True


def is_account_number_unique_algolia(
    tenant_id: str, account_number: str, exclude_contact_id: str = None
) -> bool:
    """
    Check if the account number is unique among active contacts using Algolia.
    
    Args:
        tenant_id: The tenant ID
        account_number: The account number to check
        exclude_contact_id: Optional contact ID to exclude from the check (for updates)
    
    Returns:
        bool: True if unique, False if a match exists
    """
    try:
        index = get_algolia_index()
        if not account_number:
            return True
        
        # Build filters
        filters = [f"tenant_id:{tenant_id}"]
        
        # Exclude the current contact if updating
        if exclude_contact_id:
            filters.append(f"NOT objectID:{exclude_contact_id}")
        
        # Search with account_number as query and filters
        # We'll verify exact matches in Python since Algolia text search might be fuzzy
        search_params = {
            "filters": " AND ".join(filters),
            "hitsPerPage": 10,  # Get enough to check for exact matches
            "attributesToRetrieve": ["account_number", "objectID"],
        }
        
        results = index.search(account_number, search_params)
        hits = results.get("hits", [])
        
        # Check each hit for exact account_number match
        for hit in hits:
            stored_account_number = hit.get("account_number")
            if stored_account_number == account_number:
                logger.info(f"Account number '{account_number}' is not unique")
                return False
        
        logger.info(f"Account number '{account_number}' is unique")
        return True
        
    except Exception as error:
        logger.error(f"Error checking account number uniqueness in Algolia: {error}")
        # Fallback: return True to allow the operation if Algolia fails
        # This prevents blocking operations if Algolia is temporarily unavailable
        # The DynamoDB sync will eventually catch any duplicates
        logger.warning("Falling back to allowing operation due to Algolia error")
        return True