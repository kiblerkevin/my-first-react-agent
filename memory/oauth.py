"""Mixin for OAuth token operations."""

from typing import Any

from memory.database import OAuthToken, get_session
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class OAuthMixin:
    """OAuth token persistence with encryption."""

    def save_oauth_token(
        self,
        service: str,
        access_token: str,
        blog_id: str | None = None,
        blog_url: str | None = None,
    ) -> None:
        """Save an OAuth token for a service, encrypted at rest."""
        from utils.encryption import encrypt_token

        encrypted = encrypt_token(access_token)
        session = get_session(self.engine)
        try:
            token = session.query(OAuthToken).filter_by(service=service).first()
            if token:
                token.access_token = encrypted
                token.blog_id = blog_id
                token.blog_url = blog_url
            else:
                token = OAuthToken(
                    service=service,
                    access_token=encrypted,
                    blog_id=blog_id,
                    blog_url=blog_url,
                )
                session.add(token)
            session.commit()
            logger.info(f'Saved OAuth token for {service}')
        finally:
            session.close()

    def get_oauth_token(self, service: str) -> str | None:
        """Get the OAuth token for a service, decrypting and auto-migrating if needed."""
        from utils.encryption import decrypt_token, is_encrypted

        session = get_session(self.engine)
        try:
            token = session.query(OAuthToken).filter_by(service=service).first()
            if not token:
                return None
            plaintext = decrypt_token(token.access_token)
            if not is_encrypted(token.access_token):
                from utils.encryption import encrypt_token

                token.access_token = encrypt_token(plaintext)
                session.commit()
                logger.info(f'Auto-migrated plaintext OAuth token for {service}')
            return plaintext
        finally:
            session.close()
