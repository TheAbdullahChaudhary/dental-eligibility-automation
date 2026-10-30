import boto3
import json
import os
from functools import lru_cache


@lru_cache(maxsize=None)
def get_credentials(secret_name: str) -> dict:
    """Fetch credentials from AWS Secrets Manager. Cached per secret name."""
    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
