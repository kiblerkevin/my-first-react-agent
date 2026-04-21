#!/usr/bin/env python3
"""Migrate secrets from .env to macOS Keychain.

Usage:
    python scripts/migrate_secrets.py          # migrate all keys
    python scripts/migrate_secrets.py --verify # verify keys are in Keychain
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import dotenv_values

from utils.secrets import KeychainProvider

# Keys to migrate (all sensitive values from .env)
SECRET_KEYS = [
    'ANTHROPIC_API_KEY',
    'GOOGLE_API_KEY',
    'NEWSAPI_KEY',
    'SERPAPI_KEY',
    'APPROVAL_SECRET_KEY',
    'APPROVAL_BASE_URL',
    'EMAIL_SMTP_SERVER',
    'EMAIL_SMTP_PORT',
    'EMAIL_FROM',
    'EMAIL_PASSWORD',
    'EMAIL_TO',
    'ERROR_EMAIL_TO',
    'WORDPRESS_CLIENT_ID',
    'WORDPRESS_CLIENT_SECRET',
    'WORDPRESS_URL',
]


def migrate() -> None:
    """Read .env and store each secret in Keychain."""
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        print(f'ERROR: {env_path} not found')
        sys.exit(1)

    env_values = dotenv_values(env_path)
    provider = KeychainProvider()

    migrated = 0
    skipped = 0
    for key in SECRET_KEYS:
        value = env_values.get(key)
        if not value:
            print(f'  SKIP {key} (not in .env)')
            skipped += 1
            continue
        try:
            provider.set(key, value)
            # Verify round-trip
            retrieved = provider.get(key)
            if retrieved == value:
                print(f'  OK   {key}')
                migrated += 1
            else:
                print(f'  FAIL {key} (round-trip mismatch)')
        except Exception as e:
            print(f'  FAIL {key}: {e}')

    print(f'\nMigrated: {migrated}, Skipped: {skipped}')
    print('\nNext steps:')
    print('1. Set SECRETS_PROVIDER=keychain in your .env (or config/database.yaml)')
    print('2. Remove the secret values from .env')
    print('3. Restart the approval server')


def verify() -> None:
    """Verify all secrets are accessible from Keychain."""
    provider = KeychainProvider()
    for key in SECRET_KEYS:
        value = provider.get(key)
        if value:
            print(f'  OK   {key} ({len(value)} chars)')
        else:
            print(f'  MISS {key}')


if __name__ == '__main__':
    if '--verify' in sys.argv:
        print('Verifying Keychain secrets...\n')
        verify()
    else:
        print('Migrating secrets from .env to macOS Keychain...\n')
        migrate()
