import boto3
import json
import os
from functools import lru_cache

# Local dev mock credentials — never use in production
_LOCAL_MOCK = {
    "dental/united-concordia/credentials": {"username": "demo_user", "password": "demo_pass"},
}


@lru_cache(maxsize=None)
def get_credentials(secret_name: str) -> dict:
    """Fetch credentials from AWS Secrets Manager. Falls back to mock in LOCAL_DEV mode."""
    if os.getenv("LOCAL_DEV") == "true":
        return _LOCAL_MOCK.get(secret_name, {"username": "demo", "password": "demo"})
    client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-1"))
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])
