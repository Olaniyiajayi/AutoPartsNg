"""Get part function"""

# standard imports
from json import dumps
from os import getenv

# third party imports
from boto3 import resource
from boto3.dynamodb.conditions import Key
from aws_lambda_powertools import Logger

# local imports
from utils import DecimalEncoder
from exception import handle_exceptions
from validations import DatabaseError

# Initialise response
response = {
    "statusCode": 500,
    "headers": {"Access-Control-Allow-Origin": "*"},
    "body": None,
}


# Logger
logger = Logger()

# environment variables
stage = getenv("Stage")

# table name
table_name = getenv("TableName")

# DynamoDB table
table = resource("dynamodb").Table(table_name)


def get_part(tenant_id: str, part_id: str) -> dict:
    """
    Get a single part

    Args:
        tenant_id: str
        part_id: str
    Returns:
        dict
    """
    logger.info("INSIDE GET PART")
    part = table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"PART#{part_id}"}
    ).get("Item")
    logger.info("Part %s", part)
    return part


def get_parts(tenant_id: str) -> dict:
    """
    Get all parts

    Args:
        tenant_id: str
        part_id: str
    Returns:
        dict
    """
    last_evaluated_key = None
    parts = []
    while True:
        query_params = {
            "KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant_id}")
            & Key("sk").begins_with("PART#"),
        }
        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)
        parts.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    return parts


def main(tenant_id: str, user_id: str, body: dict) -> dict:
    """
    Main Function
    Args:
        tenant_id: str
        body: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    logger.info("Query Params: %s", body)

    if not body:
        body = {}

    part_id = body.get("part_id")

    if part_id:
        try:
            # Get the part
            part = get_part(tenant_id, part_id)
            if not part:
                response["statusCode"] = 201
                response["body"] = dumps({"message": "Part not found"})
                return response
            result = part
        except Exception as error:
            logger.error("Error getting part: %s", error)
            raise DatabaseError(f"Error getting part: {error}") from error
    else:
        try:
            # Get all parts
            result = get_parts(tenant_id)
        except Exception as error:
            logger.error("Error getting parts: %s", error)
            raise DatabaseError(f"Error getting parts: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(result, cls=DecimalEncoder)
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Lambda handler function"""

    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]
    user_id = event["requestContext"]["authorizer"]["user_name"]
    body = event["queryStringParameters"]

    return main(tenant_id, user_id, body)
