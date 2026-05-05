"""Handle InvoiceUpdated events for part stock."""

from aws_lambda_powertools import Logger
from exception import handle_exceptions
from utils import apply_invoice_update, get_detail_body


logger = Logger()


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """Adjust available part quantities after an invoice update."""
    logger.info("INSIDE MAIN FUNCTION")
    invoice_change = body["body"]
    old_invoice = invoice_change.get("old", {})
    new_invoice = invoice_change.get("new", {})

    try:
        apply_invoice_update(
            tenant_id,
            old_invoice.get("items", []),
            new_invoice.get("items", []),
        )
    except Exception as error:
        logger.error("Error applying invoice update: %s", error)
        raise ValueError(f"Error applying invoice update: {error}") from error

    return {"statusCode": 200, "body": "InvoiceUpdated handled"}


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for invoice updated events."""
    body = get_detail_body(event)
    tenant_id = body["tenant_id"]
    user_id = body["user_id"]
    return main(tenant_id, user_id, body)
