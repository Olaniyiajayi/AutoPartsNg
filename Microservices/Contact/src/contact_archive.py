"""Archive contact function"""

from datetime import datetime, timezone
from json import dumps, loads
from os import getenv

from aws_lambda_powertools import Logger
from boto3 import client, resource

from utils import send_event
from exception import handle_exceptions

response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

eventbridge = client("events")
dynamodb = resource("dynamodb")

logger = Logger()
stage = getenv("Stage")
contact_table = getenv("TableName")
table = dynamodb.Table(contact_table)  # type: ignore


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for Archive customer function"""
    event_body = loads(event.get("body"))
    if "contact_id" not in event_body:
        logger.error("Error: contact_id is not in the event body")
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "contact_id is required"})
        return response

    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]

    return archive_contact(event_body, tenant_id, user_id)


@handle_exceptions
def archive_contact(event_body: dict, tenant_id: str, user_id: str) -> dict:
    """
    Step 1: Check if the contact_id is valid
    Step 2: Archive the contact from the dynamodb table
    Args:
        event_body: dict
        tenant_id: str
        user_id: str
    Returns:
        dict
    """
    logger.info("INSIDE ARCHIVE CONTACT FUNCTION")
    contact_id = event_body["contact_id"]

    # Check if the contact exists in the table
    item = table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"CONTACT#{contact_id}"}
    )
    logger.info("Item: %s", item)

    if "Item" not in item:
        logger.error("Error: Contact not found")
        response["statusCode"] = 404
        response["body"] = dumps({"Error": "Contact not found"})
        return response

    # if the contact is already archived then we will return an error
    if item["Item"].get("contact_status") == "ARCHIVED":
        logger.error("Error: Contact is already archived")
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "Contact is already archived"})
        return response

    update_expression = "SET contact_status = :contact_status, updated_at = :updated_at"
    expression_attribute_values = {
        ":contact_status": "ARCHIVED",
        ":updated_at": datetime.now(timezone.utc).isoformat(),
    }
    update_result = table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"CONTACT#{contact_id}"},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )
    logger.info("Update Result: %s", update_result)

    send_event(
        tenant_id,
        user_id,
        contact_id,
        update_result["Attributes"],
        "ContactArchived",
    )

    response["statusCode"] = 200
    response["body"] = dumps({"message": "Contact Archived successfully"})

    logger.info("Response: %s", response)
    return response
