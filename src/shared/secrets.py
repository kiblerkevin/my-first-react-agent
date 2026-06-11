"""Secrets provider for AWS Lambda using Secrets Manager.

Caches the secret JSON blob at module level so it's only fetched once per cold start.
"""

import json
import os

import boto3

_cache: dict[str, str] | None = None


def _load_secrets() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    secret_arn = os.environ.get('SECRET_ARN', '')
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_arn)
    _cache = json.loads(response['SecretString'])
    return _cache


def get_secret(key: str) -> str | None:
    """Get a secret value by key from Secrets Manager.

    Args:
        key: Secret key name within the JSON blob.

    Returns:
        Secret value, or None if not found.
    """
    return _load_secrets().get(key)
