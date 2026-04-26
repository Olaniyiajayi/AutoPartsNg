"""Get contact function"""

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


def get_contact(tenant_id: str, contact_id: str) -> dict:
    """
    Get a single contact

    Args:
        tenant_id: str
        contact_id: str
    Returns:
        dict
    """
    logger.info("INSIDE GET CONTACT")
    contact = table.get_item(
        Key={"pk": f"TENANT#{tenant_id}", "sk": f"CONTACT#{contact_id}"}
    ).get("Item")
    logger.info("Contact %s", contact)
    return contact


def get_contacts(tenant_id: str) -> dict:
    """
    Get all contacts

    Args:
        tenant_id: str
        contact_id: str
    Returns:
        dict
    """
    last_evaluated_key = None
    contacts = []
    while True:
        query_params = {
            "KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant_id}")
            & Key("sk").begins_with("CONTACT#"),
        }
        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)
        contacts.extend(response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
    return contacts


def main(tenant_id: str, query_params: dict) -> dict:
    """
    Main Function
    Args:
        tenant_id: str
        query_params: dict
    Returns:
        dict
    """
    logger.info("INSIDE MAIN FUNCTION")
    logger.info("Query Params: %s", query_params)

    if not query_params:
        query_params = {}

    contact_id = query_params.get("contact_id")

    if contact_id:
        try:
            # Get the contact
            contact = get_contact(tenant_id, contact_id)
            if not contact:
                response["statusCode"] = 201
                response["body"] = dumps({"message": "Contact not found"})
                return response
            result = contact
        except Exception as error:
            logger.error("Error getting contact: %s", error)
            raise DatabaseError(f"Error getting contact: {error}") from error
    else:
        try:
            # Get all contacts
            result = get_contacts(tenant_id)
        except Exception as error:
            logger.error("Error getting contacts: %s", error)
            raise DatabaseError(f"Error getting contacts: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(result, cls=DecimalEncoder)
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Lambda handler function"""

    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]

    return main(tenant_id, event["queryStringParameters"])
