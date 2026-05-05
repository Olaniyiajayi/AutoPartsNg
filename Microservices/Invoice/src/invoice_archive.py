"""Archive invoice function"""

from datetime import datetime, timezone
from json import dumps, loads
from os import getenv

from aws_lambda_powertools import Logger
from boto3 import resource
from exception import handle_exceptions
from utils import send_event


response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

dynamodb = resource("dynamodb")
logger = Logger()
table_name = getenv("TableName")
table = dynamodb.Table(table_name)


def get_invoice(tenant_id: str, invoice_id: str) -> dict:
    """Get the invoice from the DynamoDB table."""
    logger.info("INSIDE GET INVOICE")
    return table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"INVOICE#{invoice_id}"}
    ).get("Item")


def archive_invoice(tenant_id: str, invoice_id: str) -> dict:
    """Archive an invoice from the DynamoDB table."""
    logger.info("INSIDE ARCHIVE INVOICE FUNCTION")
    return table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"INVOICE#{invoice_id}"},
        UpdateExpression="SET invoice_status = :invoice_status, updated_at = :updated_at",
        ExpressionAttributeValues={
            ":invoice_status": "ARCHIVED",
            ":updated_at": datetime.now(timezone.utc).isoformat(),
        },
        ReturnValues="ALL_NEW",
    )


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """Main function to archive an invoice."""
    logger.info("INSIDE MAIN FUNCTION")
    if "invoice_id" not in body:
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "invoice_id is required"})
        return response

    invoice_id = body["invoice_id"]

    try:
        item = get_invoice(tenant_id, invoice_id)
    except Exception as error:
        logger.error("Error getting invoice: %s", error)
        raise ValueError(f"Error getting invoice: {error}") from error

    if not item:
        response["statusCode"] = 404
        response["body"] = dumps({"Error": "Invoice not found"})
        return response

    if item.get("invoice_status") == "ARCHIVED":
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "Invoice is already archived"})
        return response

    try:
        update_result = archive_invoice(tenant_id, invoice_id)
    except Exception as error:
        logger.error("Error archiving invoice: %s", error)
        raise ValueError(f"Error archiving invoice: {error}") from error

    try:
        send_event(
            tenant_id,
            user_id,
            invoice_id,
            {"old": item, "new": update_result["Attributes"]},
            "InvoiceDeleted",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise ValueError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps({"message": "Invoice Archived successfully"})
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for Archive invoice function."""
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = loads(event.get("body"))
    return main(tenant_id, user_id, body)
