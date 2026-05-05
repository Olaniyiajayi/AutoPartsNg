"""
Lambda function to update the part object

"""

from json import dumps, loads
from os import getenv
from decimal import Decimal

from aws_lambda_powertools import Logger
from boto3 import resource, client
from models import PartPut
from utils import (
    send_event,
    validate_payload,
    DecimalEncoder,
    is_part_name_unique_algolia,
    is_part_number_unique_algolia,
)
from exception import handle_exceptions
from validations import EventBridgeError

dynamodb = resource("dynamodb")
eventbridge = client("events")
logger = Logger()
part_table = getenv("TableName")
table = dynamodb.Table(part_table)  # type: ignore

# initialize response
response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}

def convert_floats_to_decimal(obj: any) -> any:
    """
    this function will convert all floats in a dictionary to decimals
    Args:
        obj: Any
    Returns:
        Any
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

def update_part(tenant_id: str, part_id: str, payload: dict) -> dict:
    """Updates a part in the table and returns updated fields"""
    logger.info("INSIDE UPDATE PART FUNCTION")

    # Initialize update expression components
    update_expression = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    for key, value in payload.items():
        update_expression.append(f"#{key} = :{key}")
        expression_attribute_names[f"#{key}"] = key
        expression_attribute_values[f":{key}"] = value

    update_expr = "SET " + ", ".join(update_expression)

    # Update the item in DynamoDB
    result = table.update_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )

    updated_item = result.get("Attributes")

    return updated_item


def get_part(tenant_id: str, part_id: str) -> dict:
    """
    Get the part from the table
    Args:
        tenant_id: str
        part_id: str
    Returns:
        dict
    """
    logger.info("INSIDE GET PART")
    logger.info(f"part_id: {part_id}")
    item = table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"}
    ).get("Item")
    return item


def main(tenant_id: str, user_id: str, event_body: dict):
    """
    Main function to update a part
    Args:
        tenant_id: str
        user_id: str
        event_body: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    try:
        # Validate payload
        payload = validate_payload(event_body, PartPut)
    except Exception as error:
        logger.error("Error validating payload: %s", error)
        raise ValueError(f"Error validating payload: {error}") from error

    try:
        # get part
        item = get_part(tenant_id, payload.part_id)
        if not item:
            response["statusCode"] = 404
            response["body"] = dumps({"Error": "Part not found"})
            return response
    except Exception as error:
        logger.error("Error getting part: %s", error)
        raise ValueError(f"Error getting part: {error}") from error

    try:
        # part_name must be unique
        if (
            payload.part_name is not None
            and payload.part_name != item["part_name"]
            and not is_part_name_unique_algolia(tenant_id, payload.part_name, payload.part_id)
        ):
            response["statusCode"] = 400
            response["body"] = dumps({"Error": "Part Name is not unique"})
            return response
    except Exception as error:
        logger.error("Error checking part_name: %s", error)
        raise ValueError(f"Error checking part_name: {error}") from error

    try:
        if payload.part_number is not None and payload.part_number != item.get("part_number"):
            # part_number must be unique
            if not is_part_number_unique_algolia(tenant_id, payload.part_number, payload.part_id):
                response["statusCode"] = 400
                response["body"] = dumps({"Error": "Part Number is not unique"})
                return response
    except Exception as error:
        logger.error("Error checking part_number: %s", error)
        raise ValueError(f"Error checking part_number: {error}") from error

    try:
        # update part
        result = update_part(tenant_id, payload.part_id, convert_floats_to_decimal(payload.dict()))
    except Exception as error:
        logger.error("Error updating part: %s", error)
        raise ValueError(f"Error updating part: {error}") from error

    try:
        # send event
        send_event(
            tenant_id,
            user_id,
            payload.part_id,
            result,
            "PartUpdated",
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
    """
    Handler for update part function
    Args:
        event: dict
        context: dict
    Returns:
        dict
    """
    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]

    return main(tenant_id, user_id, loads(event.get("body")))
