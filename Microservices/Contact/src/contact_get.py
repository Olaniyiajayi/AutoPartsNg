"""Get contact function"""

# standard imports
from json import dumps, loads
from os import getenv

# third party imports
from boto3 import resource
from boto3.dynamodb.conditions import Key, Attr
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


def get_contacts(tenant_id: str, contact_type: str = None, limit: int = 50, exclusive_start_key: dict = None) -> dict:
    """
    Get contacts with optional filtering and pagination
    Args:
        tenant_id: str
        contact_type: str
        limit: int
        exclusive_start_key: dict
    Returns:
        dict
    """
    logger.info("INSIDE GET CONTACTS")
    
    query_params = {
        "KeyConditionExpression": Key("pk").eq(f"TENANT#{tenant_id}")
        & Key("sk").begins_with("CONTACT#"),
        "Limit": limit
    }
    
    if contact_type:
        query_params["FilterExpression"] = Attr("contact_type").eq(contact_type)
        
    if exclusive_start_key:
        query_params["ExclusiveStartKey"] = exclusive_start_key

    try:
        db_response = table.query(**query_params)
        return {
            "items": db_response.get("Items", []),
            "last_evaluated_key": db_response.get("LastEvaluatedKey")
        }
    except Exception as error:
        logger.error("Error querying DynamoDB: %s", error)
        raise DatabaseError(f"Error getting contacts: {error}") from error


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
            # Get single contact
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
            # List contacts
            contact_type = query_params.get("contact_type")
            limit = int(query_params.get("limit", 50))
            
            # Simple pagination support
            exclusive_start_key = None
            if "last_evaluated_key" in query_params:
                try:
                    # Expecting base64 or JSON string, but for simplicity starts with JSON
                    exclusive_start_key = loads(query_params["last_evaluated_key"])
                except Exception:
                    logger.warning("Failed to parse last_evaluated_key")
            
            result = get_contacts(tenant_id, contact_type, limit, exclusive_start_key)
        except Exception as error:
            logger.error("Error listing contacts: %s", error)
            raise DatabaseError(f"Error listing contacts: {error}") from error

    response["statusCode"] = 200
    response["body"] = dumps(result, cls=DecimalEncoder)
    return response


@logger.inject_lambda_context(log_event=False)
@handle_exceptions
def handler(event, context):
    """Lambda handler function"""

    tenant_id = event["requestContext"]["authorizer"]["tenant_id"]

    return main(tenant_id, event["queryStringParameters"])
