"""
W34: Authentication & Authorization Service
JWT tokens with bcrypt password hashing and RBAC
"""

from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """
    Authentication service with JWT tokens and role-based access control

    Roles:
    - admin: Full system access, can manage users
    - operator: Can start/stop recordings, view all data
    - viewer: Read-only access to recordings and status
    """

    def __init__(self, secret_key: str = "change-this-secret-key-in-production"):
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7

    def hash_password(self, password: str) -> str:
        """
        Hash password with bcrypt (12 rounds by default)

        Args:
            password: Plain text password

        Returns:
            Bcrypt hashed password
        """
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against bcrypt hash

        Args:
            plain_password: Password to verify
            hashed_password: Bcrypt hash to verify against

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, user_id: int, email: str, role: str) -> str:
        """
        Create JWT access token (30 minute expiry)

        Args:
            user_id: User ID
            email: User email address
            role: User role (admin/operator/viewer)

        Returns:
            Encoded JWT token string
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        payload = {
            "user_id": user_id,
            "email": email,
            "role": role,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int) -> str:
        """
        Create JWT refresh token (7 day expiry)

        Args:
            user_id: User ID

        Returns:
            Encoded JWT token string
        """
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        payload = {
            "user_id": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[dict]:
        """
        Verify and decode JWT token

        Args:
            token: JWT token string

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def check_permission(self, user_role: str, required_role: str) -> bool:
        """
        Check if user has required permission

        Args:
            user_role: User's role
            required_role: Required role for operation

        Returns:
            True if user has permission, False otherwise
        """
        # Role hierarchy: admin > operator > viewer
        roles_hierarchy = {"admin": 3, "operator": 2, "viewer": 1}

        user_level = roles_hierarchy.get(user_role, 0)
        required_level = roles_hierarchy.get(required_role, 0)

        return user_level >= required_level


# Singleton instance
_auth_service: Optional[AuthService] = None

def get_auth_service() -> AuthService:
    """Get singleton auth service instance"""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


# Example usage
if __name__ == "__main__":
    auth = get_auth_service()

    # Test password hashing
    password = "SecurePassword123"
    hashed = auth.hash_password(password)
    print(f"Password: {password}")
    print(f"Hashed: {hashed}")
    print(f"Verify: {auth.verify_password(password, hashed)}")
    print()

    # Test JWT tokens
    access_token = auth.create_access_token(1, "admin@localhost", "admin")
    print(f"Access Token: {access_token[:50]}...")
    print()

    payload = auth.verify_token(access_token)
    print(f"Decoded Payload: {payload}")
    print()

    # Test permissions
    print("Permission Checks:")
    print(f"  Admin can operate: {auth.check_permission('admin', 'operator')}")
    print(f"  Operator can admin: {auth.check_permission('operator', 'admin')}")
    print(f"  Viewer can operate: {auth.check_permission('viewer', 'operator')}")
