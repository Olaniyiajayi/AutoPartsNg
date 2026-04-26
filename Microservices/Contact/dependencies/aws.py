"""
This module contains the functions for the AWS services.
"""

# standard imports
from os import getenv

from aws_lambda_powertools.utilities import parameters
from boto3 import Session
from opensearchpy import OpenSearch, RequestsHttpConnection

# third party imports
from pymysql import connect
from requests_aws4auth import AWS4Auth

# environment variables
stage = getenv("Stage")

# parameters
DB_VALUES = parameters.get_parameters(f"/{stage}/db_credentials/new")


def get_opensearch_client() -> OpenSearch:
    """
    Returns an OpenSearch client instance.

    Returns:
        OpenSearch: An OpenSearch client instance.
    """
    session = Session()
    credentials = session.get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        session.region_name,
        "es",
        session_token=credentials.token,
    )

    opensearch_endpoint = getenv(
        "OpenSearchEndpoint",
        "https://opensearch-cluster-1.cluster-ro-cyvzjzl77qzl.us-east-1.es.amazonaws.com",
    )
    return OpenSearch(
        hosts=[opensearch_endpoint],
        connection_class=RequestsHttpConnection,
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        http_compress=True,
        timeout=60,
        retry_on_timeout=True,
    )