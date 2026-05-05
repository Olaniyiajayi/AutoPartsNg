"""
Lambda function to create the part object
"""

from decimal import Decimal
from datetime import datetime, timezone
from json import dumps, loads
from os import getenv
from uuid import uuid4

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent,
)
from boto3 import client, resource
from models import Part, PartPost
from utils import (
    DecimalEncoder,
    send_event,
    validate_payload,
    is_part_name_unique_algolia,
    is_part_number_unique_algolia,
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
DEBUG = getenv("DEBUG")
RELEASE = getenv("RELEASE")


# table
table = dynamodb.Table(table_name)

# initialize response
response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

# set idempotency persistence layer
dynamodb_persistence_layer = DynamoDBPersistenceLayer(
    table_name=idempotency_table
)
idempotency_config = IdempotencyConfig(
    event_key_jmespath="body", expires_after_seconds=idempotency_expiry
)


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


def create_part_object(tenant_id: str, event_body: PartPost) -> dict:
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
    logger.info("INSIDE CREATE PART")

    # generate a unique part_id
    part_id = str(uuid4())

    item = {
        "pk": f"TENANT#{tenant_id}",
        "sk": f"PART#{part_id}",
        "part_id": part_id,
        "tenant_id": tenant_id,
        "type": "PART",
        "part_name": event_body.part_name,
        "part_number": event_body.part_number,
        "brand": event_body.brand,
        "category": event_body.category,
        "description": event_body.description,
        "quantity_available": event_body.quantity_available,
        "reorder_level": event_body.reorder_level,
        "unit_price": event_body.unit_price,
        "cost_price": event_body.cost_price,
        "part_status": "ACTIVE",
        "is_hidden": event_body.is_hidden,
        "note": event_body.note,
        "part_type": event_body.part_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info("Item: %s", item)
    return item


def store_part(item: dict) -> bool:
    """
    Store the part object in the database
    Args:
        item: dict
    Returns:
        dict
    """
    logger.info("INSIDE STORE PART")
    table.put_item(Item=convert_floats_to_decimal(item))
    return True


def main(tenant_id: str, user_id: str, body: dict):
    """
    Main function to create a part
    Args:
        tenant_id: str
        user_id: str
        body: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    try:
        # Validate payload
        payload = validate_payload(body, PartPost)
    except Exception as error:
        logger.error("Error validating payload: %s", error)
        raise ValueError(f"Error validating payload: {error}") from error

    try:
        # part_name must be unique
        if not is_part_name_unique_algolia(tenant_id, payload.part_name):
            logger.info("Error: part_name is not unique")
            response["statusCode"] = 400
            response["body"] = dumps({"Error": "Part Name is not unique"})
            return response
    except Exception as error:
        logger.error("Error checking part_name: %s", error)
        raise ValueError(f"Error checking part_name: {error}") from error

    try:
        # part_number must be unique
        if payload.part_number is not None and not is_part_number_unique_algolia(
            tenant_id, payload.part_number
        ):
            logger.info("Error: part_number is not unique")
            response["statusCode"] = 400
            response["body"] = dumps({"Error": "Part Number is not unique"})
            return response
    except Exception as error:
        logger.error("Error checking part_number: %s", error)
        raise ValueError(f"Error checking part_number: {error}") from error

    try:
        # create the part object
        item = create_part_object(tenant_id, payload)
    except Exception as error:
        logger.error("Error creating part: %s", error)
        raise ValueError(f"Error creating part: {error}") from error

    try:
        # validate the part object
        validated_item = validate_payload(item, Part)
    except Exception as error:
        logger.error("Error validating part: %s", error)
        raise ValueError(f"Error validating part: {error}") from error

    try:
        # store the part object
        store_part(validated_item.dict())
    except Exception as error:
        logger.error("Error storing part: %s", error)
        raise DatabaseError(f"Error storing part: {error}") from error

    try:
        # send the event to EventBridge
        send_event(
            tenant_id,
            user_id,
            item["part_id"],
            validated_item.dict(),
            "PartCreated",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise ValueError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(validated_item.dict(), cls=DecimalEncoder)

    return response


@idempotent(
    config=idempotency_config,
    persistence_store=dynamodb_persistence_layer,
)
@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """
    Handler for post part function
    """
    # get tenant_id from event
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = loads(event.get("body"))

    return main(tenant_id, user_id, body)
