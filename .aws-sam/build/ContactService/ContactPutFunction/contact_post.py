"""
Lambda function to create the contact object
"""

from decimal import Decimal
from datetime import datetime, timezone
from json import dumps, loads
from os import getenv
from uuid import uuid4

from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Attr, Key
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent,
)
from boto3 import client, resource
from models import Contact, ContactPost
from utils import (
    send_event,
    validate_payload,
    is_contact_name_unique_algolia,
    is_account_number_unique_algolia,
)
from exception import handle_exceptions, DatabaseError

# initialize aws clients
eventbridge = client("events")
dynamodb = resource("dynamodb")

# initialize logger
logger = Logger()

# initialize environment variables
table_name = getenv("TableName")
idempotency_expiry = int(getenv("IdempotencyExpiry"))
idempotency_table = getenv("IdempotencyTableName")
SENTRY_DNS = getenv("SENTRY_DNS")
DEBUG = getenv("DEBUG")
RELEASE = getenv("RELEASE")
TRACES_SENTRY_SAMPLE_RATE = float(getenv("TRACES_SENTRY_SAMPLE_RATE"))
PROFILE_SAMPLE_RATE = float(getenv("PROFILE_SAMPLE_RATE"))


# table
table = dynamodb.Table(table_name)

# initialize response
response = {
    "statusCode": 500,
    "headers": {"access-control-allow-origin": "*"},
    "body": None,
}

# set idempotency persistence layer
dynamodb_persistence_layer = DynamoDBPersistenceLayer(
    table_name=idempotency_table
)
idempotency_config = IdempotencyConfig(
    event_key_jmespath="body", expires_after_seconds=idempotency_expiry
)


def clean_primary_people(primary_people: list[dict]) -> list[dict]:
    """
    Cleans primary people
    Args:
        primary_people: list[dict]
    Returns:
        list[dict]
    """
    logger.info("INSIDE CLEAN PRIMARY PEOPLE FUNCTION")
    cleaned_primary_people = []

    for person in primary_people:
        if (
            person.primary_person_first_name
            or person.primary_person_last_name
            or person.primary_person_email
        ):
            cleaned_primary_people.append(person.dict())

    return cleaned_primary_people


def convert_floats_to_decimal(obj: any) -> any:
    """
    this function will convert all floats in a dictionary to decimals
    Args:
        obj: Any
    Returns:
        Any
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj


def create_contact_object(tenant_id: str, event_body: ContactPost) -> dict:
    """
    Step 1: Prepare the data for the database
    Step 2: Add the data to the dynamodb table
    Args:
        event_body: dict
        tenant_id: str
        user_id: str
    Returns:
        dict
    """
    logger.info("INSIDE CREATE CONTACT")

    # generate a unique contact_id
    contact_id = str(uuid4())

    # check if the delivery address is the same as the billing address
    same_as_delivery_address = event_body.same_as_delivery_address

    # if the delivery address is the same as the billing address,
    if same_as_delivery_address:
        billing_address = event_body.delivery_address
    else:
        billing_address = event_body.billing_address

    item = {
        "pk": f"TENANT#{tenant_id}",
        "sk": f"CONTACT#{contact_id}",
        "contact_id": contact_id,
        "tenant_id": tenant_id,
        "type": "CONTACT",
        "contact_name": event_body.contact_name,
        "contact_email": event_body.contact_email,
        "contact_phone": event_body.contact_phone,
        "contact_status": "ACTIVE",
        "is_business_contact": event_body.is_business_contact,
        "is_capricorn_member": event_body.is_capricorn_member,
        "is_on_hold": event_body.is_on_hold,
        "on_hold_at": None,
        "is_hidden": event_body.is_hidden,
        "account_number": event_body.account_number,
        "payment_type": event_body.payment_type,
        "primary_people": clean_primary_people(event_body.primary_people),
        "delivery_address": event_body.delivery_address.dict(),
        "same_as_delivery_address": event_body.same_as_delivery_address,
        "billing_address": billing_address.dict(),
        "note": event_body.note,
        "credit_limit": event_body.credit_limit,
        "block_new_invoice_if_credit_exceeded": event_body.block_new_invoice_if_credit_exceeded,
        "line_item_tax_type": event_body.line_item_tax_type,
        "sales_account": event_body.sales_account,
        "default_due_date": event_body.default_due_date,
        "contact_type": event_body.contact_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("Item: %s", item)
    return item


def store_contact(item: dict) -> bool:
    """
    Store the contact object in the database
    Args:
        item: dict
    Returns:
        dict
    """
    logger.info("INSIDE STORE CONTACT")
    table.put_item(Item=convert_floats_to_decimal(item))
    return True


def main(tenant_id: str, user_id: str, event_body: dict):
    """
    Main function to create a contact
    Args:
        tenant_id: str
        user_id: str
        event_body: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    try:
        # Validate payload
        payload = validate_payload(event_body, ContactPost)
    except Exception as error:
        logger.error("Error validating payload: %s", error)
        raise ValueError(f"Error validating payload: {error}") from error

    try:
        # contact_name must be unique
        if not is_contact_name_unique_algolia(tenant_id, payload.contact_name):
            logger.info("Error: contact_name is not unique")
            response["statusCode"] = 400
            response["body"] = dumps({"Error": "Contact Name is not unique"})
            return response
    except Exception as error:
        logger.error("Error checking contact_name: %s", error)
        raise ValueError(f"Error checking contact_name: {error}") from error

    try:
        # account_number must be unique
        if payload.account_number is not None and not is_account_number_unique_algolia(
            tenant_id, payload.account_number
        ):
            logger.info("Error: account_number is not unique")
            response["statusCode"] = 400
            response["body"] = dumps({"Error": "Account Number is not unique"})
            return response
    except Exception as error:
        logger.error("Error checking account_number: %s", error)
        raise ValueError(f"Error checking account_number: {error}") from error

    try:
        # create the contact object
        item = create_contact_object(tenant_id, payload)
    except Exception as error:
        logger.error("Error creating contact: %s", error)
        raise ValueError(f"Error creating contact: {error}") from error

    try:
        # validate the contact object
        validated_item = validate_payload(item, Contact)
    except Exception as error:
        logger.error("Error validating contact: %s", error)
        raise ValueError(f"Error validating contact: {error}") from error

    try:
        # store the contact object
        store_contact(validated_item.dict())
    except Exception as error:
        logger.error("Error storing contact: %s", error)
        raise DatabaseError(f"Error storing contact: {error}") from error

    try:
        # send the event to EventBridge
        send_event(
            tenant_id,
            user_id,
            item["contact_id"],
            validated_item.dict(),
            "ContactCreated",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise ValueError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(validated_item.dict())

    return response


@idempotent(
    config=idempotency_config,
    persistence_store=dynamodb_persistence_layer,
)
@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """
    Handler for post customer function
    """
    # get tenant_id from event
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]

    return main(tenant_id, user_id, loads(event.get("body")))
