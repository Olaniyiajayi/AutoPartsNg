"""
Lambda function to update the invoice object
"""

from datetime import datetime, timezone
from decimal import Decimal
from json import dumps, loads
from os import getenv

from aws_lambda_powertools import Logger
from boto3 import resource
from exception import handle_exceptions
from models import InvoicePut
from utils import DecimalEncoder, send_event, validate_payload
from validations import EventBridgeError


dynamodb = resource("dynamodb")
logger = Logger()
table_name = getenv("TableName")
table = dynamodb.Table(table_name)

response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}


def convert_floats_to_decimal(obj: any) -> any:
    """Convert floats in nested objects to decimals for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    return obj


def get_invoice(tenant_id: str, invoice_id: str) -> dict:
    """Get the invoice from the table."""
    logger.info("INSIDE GET INVOICE")
    return table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"INVOICE#{invoice_id}"}
    ).get("Item")


def update_invoice(tenant_id: str, invoice_id: str, payload: dict) -> dict:
    """Updates an invoice in the table and returns updated fields."""
    logger.info("INSIDE UPDATE INVOICE FUNCTION")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    for key, value in payload.items():
        update_expression.append(f"#{key} = :{key}")
        expression_attribute_names[f"#{key}"] = key
        expression_attribute_values[f":{key}"] = value

    result = table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"INVOICE#{invoice_id}"},
        UpdateExpression="SET " + ", ".join(update_expression),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )
    return result.get("Attributes")


def main(tenant_id: str, user_id: str, body: dict):
    """Main function to update an invoice."""
    logger.info("INSIDE MAIN FUNCTION")
    try:
        payload = validate_payload(body, InvoicePut)
    except Exception as error:
        logger.error("Error validating payload: %s", error)
        raise ValueError(f"Error validating payload: {error}") from error

    try:
        existing_invoice = get_invoice(tenant_id, payload.invoice_id)
        if not existing_invoice:
            response["statusCode"] = 404
            response["body"] = dumps({"Error": "Invoice not found"})
            return response
    except Exception as error:
        logger.error("Error getting invoice: %s", error)
        raise ValueError(f"Error getting invoice: {error}") from error

    try:
        result = update_invoice(
            tenant_id,
            payload.invoice_id,
            convert_floats_to_decimal(payload.dict()),
        )
    except Exception as error:
        logger.error("Error updating invoice: %s", error)
        raise ValueError(f"Error updating invoice: {error}") from error

    try:
        send_event(
            tenant_id,
            user_id,
            payload.invoice_id,
            {"old": existing_invoice, "new": result},
            "InvoiceUpdated",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise EventBridgeError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(result, cls=DecimalEncoder)
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for update invoice function."""
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = loads(event.get("body"))
    return main(tenant_id, user_id, body)
