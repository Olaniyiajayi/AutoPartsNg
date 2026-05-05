"""Archive part function"""

from datetime import datetime, timezone
from json import dumps, loads
from os import getenv

from aws_lambda_powertools import Logger
from boto3 import resource

from utils import send_event
from exception import handle_exceptions

response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

dynamodb = resource("dynamodb")

logger = Logger()
stage = getenv("Stage")
part_table = getenv("TableName")
table = dynamodb.Table(part_table)  # type: ignore


def get_part(tenant_id: str, part_id: str) -> dict:
    """Get the part from the table."""
    logger.info("INSIDE GET PART")
    return table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"}
    ).get("Item")


def archive_part(tenant_id: str, part_id: str) -> dict:
    """
    Archive the part from the dynamodb table.

    Args:
        tenant_id: str
        part_id: str
    Returns:
        dict
    """
    logger.info("INSIDE ARCHIVE PART FUNCTION")
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
    return update_result["Attributes"]


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """
    Main function to archive a part.

    Args:
        tenant_id: str
        user_id: str
        body: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    if "part_id" not in body:
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "part_id is required"})
        return response

    part_id = body["part_id"]

    try:
        item = get_part(tenant_id, part_id)
    except Exception as error:
        logger.error("Error getting part: %s", error)
        raise ValueError(f"Error getting part: {error}") from error

    if not item:
        response["statusCode"] = 404
        response["body"] = dumps({"Error": "Part not found"})
        return response

    if item.get("part_status") == "ARCHIVED":
        response["statusCode"] = 400
        response["body"] = dumps({"Error": "Part is already archived"})
        return response

    try:
        result = archive_part(tenant_id, part_id)
    except Exception as error:
        logger.error("Error archiving part: %s", error)
        raise ValueError(f"Error archiving part: {error}") from error

    try:
        send_event(
            tenant_id,
            user_id,
            part_id,
            result,
            "PartArchived",
        )
    except Exception as error:
        logger.error("Error sending event: %s", error)
        raise ValueError(f"Error sending event: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps({"message": "Part Archived successfully"})
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Handler for Archive part function."""
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = loads(event.get("body"))

    return main(tenant_id, user_id, body)
