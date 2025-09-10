"""
User Service - Microservices Example
====================================

This example demonstrates a user service in a microservices architecture,
showing how Understand-First helps with distributed system understanding.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import hashlib
import secrets

import aiohttp
import asyncpg
from pydantic import BaseModel, EmailStr, validator

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration for the user service."""

    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class UserCreateRequest(BaseModel):
    """Request model for creating a new user."""

    email: EmailStr
    password: str
    first_name: str
    last_name: str

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    is_active: bool


class UserService:
    """Core user service handling user management operations."""

    def __init__(self, db_config: DatabaseConfig, auth_service_url: str):
        self.db_config = db_config
        self.auth_service_url = auth_service_url
        self._db_pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool."""
        self._db_pool = await asyncpg.create_pool(self.db_config.dsn, min_size=5, max_size=20)
        logger.info("User service initialized with database pool")

    async def close(self):
        """Close database connection pool."""
        if self._db_pool:
            await self._db_pool.close()
            logger.info("User service database pool closed")

    async def create_user(self, user_data: UserCreateRequest) -> UserResponse:
        """Create a new user with validation and password hashing."""
        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if user already exists
                existing_user = await conn.fetchrow(
                    "SELECT id FROM users WHERE email = $1", user_data.email
                )
                if existing_user:
                    raise ValueError("User with this email already exists")

                # Hash password
                password_hash = self._hash_password(user_data.password)

                # Create user record
                user_id = secrets.token_urlsafe(16)
                now = datetime.utcnow()

                await conn.execute(
                    """
                    INSERT INTO users (id, email, password_hash, first_name, last_name, created_at, is_active)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    user_id,
                    user_data.email,
                    password_hash,
                    user_data.first_name,
                    user_data.last_name,
                    now,
                    True,
                )

                # Notify auth service
                await self._notify_auth_service(
                    "user_created", {"user_id": user_id, "email": user_data.email}
                )

                logger.info(f"Created user {user_id} with email {user_data.email}")

                return UserResponse(
                    id=user_id,
                    email=user_data.email,
                    first_name=user_data.first_name,
                    last_name=user_data.last_name,
                    created_at=now,
                    is_active=True,
                )

    async def get_user(self, user_id: str) -> Optional[UserResponse]:
        """Retrieve user by ID."""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, first_name, last_name, created_at, is_active FROM users WHERE id = $1",
                user_id,
            )

            if not row:
                return None

            return UserResponse(
                id=row["id"],
                email=row["email"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                created_at=row["created_at"],
                is_active=row["is_active"],
            )

    async def get_user_by_email(self, email: str) -> Optional[UserResponse]:
        """Retrieve user by email address."""
        async with self._db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, email, first_name, last_name, created_at, is_active FROM users WHERE email = $1",
                email,
            )

            if not row:
                return None

            return UserResponse(
                id=row["id"],
                email=row["email"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                created_at=row["created_at"],
                is_active=row["is_active"],
            )

    async def update_user(self, user_id: str, updates: Dict[str, Any]) -> Optional[UserResponse]:
        """Update user information."""
        allowed_fields = {"first_name", "last_name", "email"}
        update_fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not update_fields:
            raise ValueError("No valid fields to update")

        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Check if user exists
                existing_user = await self.get_user(user_id)
                if not existing_user:
                    return None

                # Build update query
                set_clauses = []
                values = []
                param_count = 1

                for field, value in update_fields.items():
                    set_clauses.append(f"{field} = ${param_count}")
                    values.append(value)
                    param_count += 1

                values.append(user_id)

                await conn.execute(
                    f"""
                    UPDATE users 
                    SET {', '.join(set_clauses)}, updated_at = ${param_count}
                    WHERE id = ${param_count + 1}
                """,
                    *values,
                    datetime.utcnow(),
                )

                # Notify auth service if email changed
                if "email" in update_fields:
                    await self._notify_auth_service(
                        "user_updated", {"user_id": user_id, "email": update_fields["email"]}
                    )

                logger.info(f"Updated user {user_id} with fields: {list(update_fields.keys())}")

                return await self.get_user(user_id)

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        async with self._db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET is_active = false, updated_at = $1 WHERE id = $2",
                datetime.utcnow(),
                user_id,
            )

            if result == "UPDATE 1":
                await self._notify_auth_service("user_deactivated", {"user_id": user_id})
                logger.info(f"Deactivated user {user_id}")
                return True

            return False

    async def list_users(self, limit: int = 50, offset: int = 0) -> List[UserResponse]:
        """List users with pagination."""
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email, first_name, last_name, created_at, is_active
                FROM users
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
            """,
                limit,
                offset,
            )

            return [
                UserResponse(
                    id=row["id"],
                    email=row["email"],
                    first_name=row["first_name"],
                    last_name=row["last_name"],
                    created_at=row["created_at"],
                    is_active=row["is_active"],
                )
                for row in rows
            ]

    def _hash_password(self, password: str) -> str:
        """Hash password using secure method."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return f"{salt}:{password_hash.hex()}"

    async def _notify_auth_service(self, event: str, data: Dict[str, Any]):
        """Notify auth service of user events."""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"event": event, "data": data, "timestamp": datetime.utcnow().isoformat()}

                async with session.post(
                    f"{self.auth_service_url}/events",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Auth service notification failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to notify auth service: {str(e)}")


class UserServiceAPI:
    """HTTP API wrapper for the user service."""

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def handle_create_user(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user creation API request."""
        try:
            user_data = UserCreateRequest(**request_data)
            user = await self.user_service.create_user(user_data)
            return {"success": True, "user": user.dict()}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            return {"success": False, "error": "Internal server error"}

    async def handle_get_user(self, user_id: str) -> Dict[str, Any]:
        """Handle get user API request."""
        try:
            user = await self.user_service.get_user(user_id)
            if user:
                return {"success": True, "user": user.dict()}
            else:
                return {"success": False, "error": "User not found"}
        except Exception as e:
            logger.error(f"Error getting user: {str(e)}")
            return {"success": False, "error": "Internal server error"}

    async def handle_update_user(self, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Handle user update API request."""
        try:
            user = await self.user_service.update_user(user_id, updates)
            if user:
                return {"success": True, "user": user.dict()}
            else:
                return {"success": False, "error": "User not found"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            return {"success": False, "error": "Internal server error"}
