"""Handle InvoiceDeleted events for part stock."""

from aws_lambda_powertools import Logger
from exception import handle_exceptions
from utils import apply_invoice_items, get_detail_body


logger = Logger()


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """Restore available part quantities when an invoice is deleted."""
    logger.info("INSIDE MAIN FUNCTION")
    invoice_change = body["body"]
    old_invoice = invoice_change.get("old", invoice_change)

    try:
        apply_invoice_items(tenant_id, old_invoice.get("items", []), 1)
    except Exception as error:
        logger.error("Error applying invoice items: %s", error)
        raise ValueError(f"Error applying invoice items: {error}") from error

    return {"statusCode": 200, "body": "InvoiceDeleted handled"}


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for invoice deleted events."""
    body = get_detail_body(event)
    tenant_id = body["tenant_id"]
    user_id = body["user_id"]
    return main(tenant_id, user_id, body)
