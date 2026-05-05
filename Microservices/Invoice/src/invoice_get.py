"""Get invoice function"""

from json import dumps
from os import getenv

from aws_lambda_powertools import Logger
from boto3 import resource
from boto3.dynamodb.conditions import Key
from exception import handle_exceptions
from utils import DecimalEncoder
from validations import DatabaseError


response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

logger = Logger()
table_name = getenv("TableName")
table = resource("dynamodb").Table(table_name)


def get_invoice(tenant_id: str, invoice_id: str) -> dict:
    """Get a single invoice."""
    logger.info("INSIDE GET INVOICE")
    return table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"INVOICE#{invoice_id}"}
    ).get("Item")


def get_invoices(tenant_id: str) -> list:
    """Get all invoices for a tenant."""
    last_evaluated_key = None
    invoices = []
    while True:
        query_params = {
            "KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant_id}")
            & Key("sk").begins_with("INVOICE#"),
        }
        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        result = table.query(**query_params)
        invoices.extend(result.get("Items", []))
        last_evaluated_key = result.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    return invoices


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """Main function."""
    logger.info("INSIDE MAIN FUNCTION")
    if not body:
        body = {}

    invoice_id = body.get("invoice_id")
    if invoice_id:
        try:
            invoice = get_invoice(tenant_id, invoice_id)
            if not invoice:
                response["statusCode"] = 201
                response["body"] = dumps({"message": "Invoice not found"})
                return response
            result = invoice
        except Exception as error:
            logger.error("Error getting invoice: %s", error)
            raise DatabaseError(f"Error getting invoice: {error}") from error
    else:
        try:
            result = get_invoices(tenant_id)
        except Exception as error:
            logger.error("Error getting invoices: %s", error)
            raise DatabaseError(f"Error getting invoices: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(result, cls=DecimalEncoder)
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Lambda handler function."""
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = event["queryStringParameters"]
    return main(tenant_id, user_id, body)
