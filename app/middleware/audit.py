"""Audit Logging Middleware."""
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.auth.models import AuditLog
from app.config import get_settings
from jose import jwt, JWTError

logger = logging.getLogger(__name__)
settings = get_settings()

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Log only state-changing methods + successful responses
        if request.method in ["POST", "PUT", "PATCH", "DELETE"] and 200 <= response.status_code < 300:
            try:
                # Extract user from token
                auth_header = request.headers.get("Authorization")
                user_id = None
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header.split(" ")[1]
                    try:
                        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                        user_id = payload.get("sub")
                        if user_id:
                            user_id = int(user_id)
                    except JWTError:
                        pass

                # Cookie fallback
                if not user_id:
                     token = request.cookies.get("access_token")
                     if token:
                         try:
                            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                            user_id = payload.get("sub")
                            if user_id:
                                user_id = int(user_id)
                         except (JWTError, ValueError, TypeError) as e:
                             logger.debug("Failed to decode cookie token for audit: %s", e)

                if user_id:
                    self.log_action(user_id, request)
            except Exception as e:
                logger.error("Audit Log Error: %s", e)

        return response

    def log_action(self, user_id: int, request: Request):
        db = SessionLocal()
        try:
            # Simple audit log
            action = f"{request.method} {request.url.path}"
            # Extract ID from path if possible, e.g. /api/properties/123
            path_parts = request.url.path.strip("/").split("/")
            entity_type = path_parts[1] if len(path_parts) > 1 else "Unknown"
            entity_id = None
            if len(path_parts) > 2 and path_parts[-1].isdigit():
                entity_id = int(path_parts[-1])

            log = AuditLog(
                user_id=user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                ip_address=request.client.host
            )
            db.add(log)
            db.commit()
        except Exception as e:
            logger.error("Failed to write audit log: %s", e)
        finally:
            db.close()
