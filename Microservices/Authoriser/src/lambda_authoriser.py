"""
This lambda function is primarily responsible for authorizating the users request
Main Logic:
    - Validate the jwt token
    - Create a policy object
    - Create a a context object
    - Combine the policy and context objects and return to the api gateway
"""
import json
import time
import urllib.request
from os import environ

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters
from jose import jwk, jwt
from jose.utils import base64url_decode

logger = Logger()
stage = environ["Stage"]

region = parameters.get_parameter(f"/{stage}/cognito/REGION")
userpool_id = parameters.get_parameter(f"/{stage}/cognito/USER_POOL")
app_client_id = parameters.get_parameter(f"/{stage}/cognito/CLIENT_ID")


@logger.inject_lambda_context(log_event=False)
def handler(event, context):
    """Entry point for the authorizer

    Args:
        event (_type_): event data for the api call

    Returns:
        policy_json: tells the api gateway that the user has been authorised
    """
    logger.info("Event: %s", event)
    # get JWT token after Bearer from authorization
    token = event["authorizationToken"].split(" ")

    if token[0] != "Bearer":
        raise Exception("Authorization header should have a format Bearer <JWT> Token")

    jwt_bearer_token = token[1]
    logger.info("Method ARN: " + event["methodArn"])

    # only to get tenant id to get user pool info
    unauthorized_claims = jwt.get_unverified_claims(jwt_bearer_token)
    logger.info(unauthorized_claims)

    # get keys for tenant user pool to validate
    keys_url = f"https://cognito-idp.{region}.amazonaws.com/{userpool_id}/.well-known/jwks.json"

    with urllib.request.urlopen(keys_url) as f:
        response = f.read()
    keys = json.loads(response.decode("utf-8"))["keys"]

    # authenticate against cognito user pool using the key
    response = validate_jwt(jwt_bearer_token, app_client_id, keys)

    # get authenticated claims
    if response is False:
        logger.error("Unauthorized")
        raise Exception("Unauthorized")
    else:
        logger.info(response)
        principal_id = response["sub"]
        user_name = response["cognito:username"]
        tenant_id = response["custom:tenant_id"]

    result = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": "arn:aws:execute-api:*:*:*",
                }
            ],
        },
    }
    context = {
        "user_name": user_name,
        "tenant_id": tenant_id,
    }
    result["context"] = context

    return result


def validate_jwt(token, app_client_id, keys):
    """validat the jwt token

    Args:
        token (_type_): _description_
        app_client_id (_type_): _description_
        keys (_type_): _description_

    Returns:
        _type_: _description_
    """
    # get the kid from the headers prior to verification
    headers = jwt.get_unverified_headers(token)
    kid = headers["kid"]

    # search for the kid in the downloaded public keys
    key_index = -1
    len_keys = len(keys)
    for i in range(len_keys):
        if kid == keys[i]["kid"]:
            key_index = i
            break

    if key_index == -1:
        logger.info("Public key not found in jwks.json")
        return False

    # construct the public key
    public_key = jwk.construct(keys[key_index])

    # get the last two sections of the token,
    # message and signature (encoded in base64)
    message, encoded_signature = str(token).rsplit(".", 1)

    # decode the signature
    decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))

    # verify the signature
    if not public_key.verify(message.encode("utf8"), decoded_signature):
        logger.info("Signature verification failed")
        return False

    logger.info("Signature successfully verified")

    # since we passed the verification, we can now safely
    # use the unverified claims
    claims = jwt.get_unverified_claims(token)

    # additionally we can verify the token expiration
    if time.time() > claims["exp"]:
        logger.info("Token is expired")
        return False

    # and the Audience  (use claims['client_id'] if verifying an access token)
    if claims["aud"] != app_client_id:
        logger.info("Token was not issued for this audience")
        return False

    # now we can use the claims
    logger.info(claims)
    return claims
