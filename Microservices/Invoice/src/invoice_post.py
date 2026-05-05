"""
Lambda function to create the invoice object
"""

from datetime import datetime, timezone
from decimal import Decimal
from json import dumps, loads
from os import getenv
from uuid import uuid4

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.idempotency import (
    DynamoDBPersistenceLayer,
    IdempotencyConfig,
    idempotent,
)
from boto3 import resource
from exception import handle_exceptions, DatabaseError
from models import Invoice, InvoicePost
from utils import DecimalEncoder, send_event, validate_payload


dynamodb = resource("dynamodb")
logger = Logger()

table_name = getenv("TableName")
idempotency_expiry = int(getenv("IdempotencyExpiry"))
idempotency_table = getenv("IdempotencyTableName")
table = dynamodb.Table(table_name)

response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

dynamodb_persistence_layer = DynamoDBPersistenceLayer(table_name=idempotency_table)
idempotency_config = IdempotencyConfig(
    event_key_jmespath="body", expires_after_seconds=idempotency_expiry
)


def convert_floats_to_decimal(obj: any) -> any:
    """Convert floats in nested objects to decimals for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj


def create_invoice_object(tenant_id: str, event_body: InvoicePost) -> dict:
    """Prepare invoice data for storage."""
    logger.info("INSIDE CREATE INVOICE")
    invoice_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    return {
        "pk": f"TENANT#{tenant_id}",
        "sk": f"INVOICE#{invoice_id}",
        "invoice_id": invoice_id,
        "tenant_id": tenant_id,
        "type": "INVOICE",
        "invoice_number": event_body.invoice_number,
        "contact_id": event_body.contact_id,
        "invoice_status": event_body.invoice_status,
        "items": [item.dict() for item in event_body.items],
        "subtotal": event_body.subtotal,
        "tax": event_body.tax,
        "total": event_body.total,
        "note": event_body.note,
        "created_at": now,
        "updated_at": now,
    }


def store_invoice(item: dict) -> bool:
    """Store the invoice object in the database."""
    logger.info("INSIDE STORE INVOICE")
    table.put_item(Item=convert_floats_to_decimal(item))
    return True


def main(tenant_id: str, user_id: str, body: dict):
    """Main function to create an invoice."""
    logger.info("INSIDE MAIN FUNCTION")
    try:
        payload = validate_payload(body, InvoicePost)
    except Exception as error:
        logger.error("Error validating payload: %s", error)
        raise ValueError(f"Error validating payload: {error}") from error

    try:
        item = create_invoice_object(tenant_id, payload)
    except Exception as error:
        logger.error("Error creating invoice: %s", error)
        raise ValueError(f"Error creating invoice: {error}") from error

    try:
        validated_item = validate_payload(item, Invoice)
    except Exception as error:
        logger.error("Error validating invoice: %s", error)
        raise ValueError(f"Error validating invoice: {error}") from error

    try:
        store_invoice(validated_item.dict())
    except Exception as error:
        logger.error("Error storing invoice: %s", error)
        raise DatabaseError(f"Error storing invoice: {error}") from error

    try:
        send_event(
            tenant_id,
            user_id,
            item["invoice_id"],
            validated_item.dict(),
            "InvoiceCreated",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise ValueError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(validated_item.dict(), cls=DecimalEncoder)
    return response


@idempotent(config=idempotency_config, persistence_store=dynamodb_persistence_layer)
@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for post invoice function."""
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = loads(event.get("body"))
    return main(tenant_id, user_id, body)
