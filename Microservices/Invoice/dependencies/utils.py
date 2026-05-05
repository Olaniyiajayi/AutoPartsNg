"""
Invoice utils for the invoice service
"""

from decimal import Decimal
from json import JSONEncoder, dumps
from os import environ
from time import time
from typing import Any
from uuid import uuid4

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import ValidationError, parse
from boto3 import client


logger = Logger()
EVENT_BUS_NAME = environ["EventBusName"]
eventbridge = client("events")


class DecimalEncoder(JSONEncoder):
    """Handle decimal encoding"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def generate_xray_trace_header() -> str:
    """Generate an X-Ray trace header"""
    logger.info("INSIDE GENERATE XRAY TRACE HEADER FUNCTION")
    epoch = int(time())
    unique_id = uuid4().hex[:24]
    root = f"1-{epoch:08x}-{unique_id}"
    parent = uuid4().hex[:16]
    return f"Root=InvoiceService;{root};Parent={parent};Sampled=1"


def send_event(
    tenant_id: str,
    user_id: str,
    object_id: str,
    body: dict,
    detail_type: str,
) -> None:
    """Send an invoice event to EventBridge."""
    logger.info("INSIDE SEND EVENT FUNCTION")
    event = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "id": object_id,
        "body": body,
    }
    event_str = dumps(event, cls=DecimalEncoder)
    event_bridge_response = eventbridge.put_events(
        Entries=[
            {
                "Source": "INVOICE",
                "DetailType": detail_type,
                "Detail": event_str,
                "TraceHeader": generate_xray_trace_header(),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )
    logger.info("EventBridge: %s", event_bridge_response)


def validate_payload(event: dict, model: Any) -> dict:
    """Validate the input payload against a given model."""
    logger.info("INSIDE VALIDATE PAYLOAD FUNCTION")
    try:
        logger.info("Payload to validate: %s", event)
        return parse(event=event, model=model)
    except ValidationError as error:
        raise ValueError(error) from error
