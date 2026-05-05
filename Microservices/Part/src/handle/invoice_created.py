"""Handle InvoiceCreated events for part stock."""

from aws_lambda_powertools import Logger
from exception import handle_exceptions
from utils import apply_invoice_items, get_detail_body


logger = Logger()


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """Reduce available part quantities for a created invoice."""
    logger.info("INSIDE MAIN FUNCTION")
    invoice = body["body"]

    try:
        apply_invoice_items(tenant_id, invoice.get("items", []), -1)
    except Exception as error:
        logger.error("Error applying invoice items: %s", error)
        raise ValueError(f"Error applying invoice items: {error}") from error

    return {"statusCode": 200, "body": "InvoiceCreated handled"}


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for invoice created events."""
    body = get_detail_body(event)
    tenant_id = body["tenant_id"]
    user_id = body["user_id"]
    return main(tenant_id, user_id, body)
