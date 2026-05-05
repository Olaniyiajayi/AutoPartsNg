"""Archive part function"""

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
part_table = getenv("TableName")
table = dynamodb.Table(part_table)  # type: ignore


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for Archive part function"""
    event_body = loads(event.get("body"))
    if "part_id" not in event_body:
        logger.error("Error: part_id is not in the event body")
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "part_id is required"})
        return response

    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]

    return archive_part(event_body, tenant_id, user_id)


@handle_exceptions
def archive_part(event_body: dict, tenant_id: str, user_id: str) -> dict:
    """
    Step 1: Check if the part_id is valid
    Step 2: Archive the part from the dynamodb table
    Args:
        event_body: dict
        tenant_id: str
        user_id: str
    Returns:
        dict
    """
    logger.info("INSIDE ARCHIVE PART FUNCTION")
    part_id = event_body["part_id"]

    # Check if the part exists in the table
    item = table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"}
    )
    logger.info("Item: %s", item)

    if "Item" not in item:
        logger.error("Error: Part not found")
        response["statusCode"] = 404
        response["body"] = dumps({"Error": "Part not found"})
        return response

    # if the part is already archived then we will return an error
    if item["Item"].get("part_status") == "ARCHIVED":
        logger.error("Error: Part is already archived")
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "Part is already archived"})
        return response

    update_expression = "SET part_status = :part_status, updated_at = :updated_at"
    expression_attribute_values = {
        ":part_status": "ARCHIVED",
        ":updated_at": datetime.now(timezone.utc).isoformat(),
    }
    update_result = table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )
    logger.info("Update Result: %s", update_result)

    send_event(
        tenant_id,
        user_id,
        part_id,
        update_result["Attributes"],
        "PartArchived",
    )

    response["statusCode"] = 200
    response["body"] = dumps({"message": "Part Archived successfully"})

    logger.info("Response: %s", response)
    return response
