"""
Order Service - Microservices Example
====================================

This example demonstrates a complete order service in a microservices architecture,
showing how Understand-First helps with distributed system understanding.
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import asyncpg
from pydantic import BaseModel, validator
import redis.asyncio as redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass
class OrderItem:
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float


@dataclass
class Order:
    id: str
    user_id: str
    status: OrderStatus
    payment_status: PaymentStatus
    items: List[OrderItem]
    total_amount: float
    shipping_address: Dict[str, str]
    billing_address: Dict[str, str]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


class OrderCreateRequest(BaseModel):
    user_id: str
    items: List[Dict[str, Any]]
    shipping_address: Dict[str, str]
    billing_address: Dict[str, str]
    payment_method: str

    @validator("items")
    def validate_items(cls, v):
        if not v:
            raise ValueError("Order must have at least one item")
        return v


class OrderUpdateRequest(BaseModel):
    status: Optional[OrderStatus] = None
    payment_status: Optional[PaymentStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class OrderService:
    """Core order service handling order management operations."""

    def __init__(self, db_config: Dict[str, Any], redis_config: Dict[str, Any]):
        self.db_config = db_config
        self.redis_config = redis_config
        self._db_pool: Optional[asyncpg.Pool] = None
        self._redis: Optional[redis.Redis] = None
        self._http_session: Optional[aiohttp.ClientSession] = None

        # External service URLs
        self.user_service_url = "http://user-service:8001"
        self.payment_service_url = "http://payment-service:8002"
        self.inventory_service_url = "http://inventory-service:8003"
        self.notification_service_url = "http://notification-service:8004"

    async def initialize(self):
        """Initialize database and Redis connections."""
        # Initialize database pool
        self._db_pool = await asyncpg.create_pool(
            host=self.db_config["host"],
            port=self.db_config["port"],
            database=self.db_config["database"],
            user=self.db_config["user"],
            password=self.db_config["password"],
            min_size=5,
            max_size=20,
        )

        # Initialize Redis
        self._redis = redis.Redis(
            host=self.redis_config["host"],
            port=self.redis_config["port"],
            password=self.redis_config.get("password"),
            decode_responses=True,
        )

        # Initialize HTTP session
        self._http_session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        logger.info("Order service initialized")

    async def close(self):
        """Close all connections."""
        if self._db_pool:
            await self._db_pool.close()
        if self._redis:
            await self._redis.close()
        if self._http_session:
            await self._http_session.close()
        logger.info("Order service connections closed")

    async def create_order(self, order_data: OrderCreateRequest) -> Order:
        """Create a new order with validation and inventory checks."""
        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Validate user exists
                await self._validate_user(order_data.user_id)

                # Validate and reserve inventory
                validated_items = await self._validate_and_reserve_inventory(order_data.items)

                # Calculate total amount
                total_amount = sum(item["total_price"] for item in validated_items)

                # Create order
                order_id = str(uuid.uuid4())
                order = Order(
                    id=order_id,
                    user_id=order_data.user_id,
                    status=OrderStatus.PENDING,
                    payment_status=PaymentStatus.PENDING,
                    items=[OrderItem(**item) for item in validated_items],
                    total_amount=total_amount,
                    shipping_address=order_data.shipping_address,
                    billing_address=order_data.billing_address,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    metadata={
                        "payment_method": order_data.payment_method,
                        "source": "api",
                        "version": "1.0",
                    },
                )

                # Save to database
                await self._save_order_to_db(conn, order)

                # Cache order
                await self._cache_order(order)

                # Process payment
                payment_result = await self._process_payment(order)
                if payment_result["success"]:
                    order.payment_status = PaymentStatus.COMPLETED
                    order.status = OrderStatus.CONFIRMED
                else:
                    order.payment_status = PaymentStatus.FAILED
                    # Release inventory
                    await self._release_inventory(validated_items)

                # Update order in database
                await self._update_order_in_db(conn, order)
                await self._cache_order(order)

                # Send notifications
                await self._send_order_notifications(order)

                logger.info(f"Created order {order_id} for user {order_data.user_id}")
                return order

    async def get_order(self, order_id: str, user_id: Optional[str] = None) -> Optional[Order]:
        """Retrieve order by ID with optional user validation."""
        # Try cache first
        cached_order = await self._get_cached_order(order_id)
        if cached_order:
            if user_id and cached_order.user_id != user_id:
                return None
            return cached_order

        # Fallback to database
        async with self._db_pool.acquire() as conn:
            order = await self._get_order_from_db(conn, order_id, user_id)
            if order:
                await self._cache_order(order)
            return order

    async def update_order(
        self, order_id: str, updates: OrderUpdateRequest, user_id: Optional[str] = None
    ) -> Optional[Order]:
        """Update order status and metadata."""
        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                # Get existing order
                order = await self._get_order_from_db(conn, order_id, user_id)
                if not order:
                    return None

                # Validate status transition
                if updates.status and not self._is_valid_status_transition(
                    order.status, updates.status
                ):
                    raise ValueError(
                        f"Invalid status transition from {order.status} to {updates.status}"
                    )

                # Update order
                if updates.status:
                    order.status = updates.status
                if updates.payment_status:
                    order.payment_status = updates.payment_status
                if updates.metadata:
                    order.metadata.update(updates.metadata)

                order.updated_at = datetime.utcnow()

                # Save to database
                await self._update_order_in_db(conn, order)

                # Update cache
                await self._cache_order(order)

                # Send notifications for status changes
                if updates.status:
                    await self._send_status_notification(order)

                logger.info(f"Updated order {order_id}: {updates.status or 'metadata'}")
                return order

    async def list_orders(
        self,
        user_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """List orders with filtering and pagination."""
        async with self._db_pool.acquire() as conn:
            orders = await self._get_orders_from_db(conn, user_id, status, limit, offset)

            # Cache orders
            for order in orders:
                await self._cache_order(order)

            return orders

    async def cancel_order(
        self, order_id: str, user_id: str, reason: str = "User requested"
    ) -> bool:
        """Cancel an order and release inventory."""
        async with self._db_pool.acquire() as conn:
            async with conn.transaction():
                order = await self._get_order_from_db(conn, order_id, user_id)
                if not order:
                    return False

                if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
                    return False

                # Update order status
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.utcnow()
                order.metadata["cancellation_reason"] = reason
                order.metadata["cancelled_at"] = datetime.utcnow().isoformat()

                # Release inventory
                await self._release_inventory([asdict(item) for item in order.items])

                # Process refund if payment was completed
                if order.payment_status == PaymentStatus.COMPLETED:
                    await self._process_refund(order)

                # Save to database
                await self._update_order_in_db(conn, order)
                await self._cache_order(order)

                # Send cancellation notification
                await self._send_cancellation_notification(order)

                logger.info(f"Cancelled order {order_id} for user {user_id}")
                return True

    async def _validate_user(self, user_id: str) -> None:
        """Validate user exists via user service."""
        try:
            async with self._http_session.get(
                f"{self.user_service_url}/users/{user_id}"
            ) as response:
                if response.status != 200:
                    raise ValueError(f"User {user_id} not found")
        except aiohttp.ClientError as e:
            logger.error(f"Error validating user {user_id}: {e}")
            raise ValueError("Unable to validate user")

    async def _validate_and_reserve_inventory(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Validate inventory availability and reserve items."""
        try:
            payload = {"items": items, "action": "reserve"}
            async with self._http_session.post(
                f"{self.inventory_service_url}/inventory/reserve", json=payload
            ) as response:
                if response.status != 200:
                    data = await response.json()
                    raise ValueError(
                        f"Inventory validation failed: {data.get('error', 'Unknown error')}"
                    )

                result = await response.json()
                return result["validated_items"]
        except aiohttp.ClientError as e:
            logger.error(f"Error validating inventory: {e}")
            raise ValueError("Unable to validate inventory")

    async def _release_inventory(self, items: List[Dict[str, Any]]) -> None:
        """Release reserved inventory."""
        try:
            payload = {"items": items, "action": "release"}
            async with self._http_session.post(
                f"{self.inventory_service_url}/inventory/release", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to release inventory: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error releasing inventory: {e}")

    async def _process_payment(self, order: Order) -> Dict[str, Any]:
        """Process payment via payment service."""
        try:
            payload = {
                "order_id": order.id,
                "amount": order.total_amount,
                "currency": "USD",
                "payment_method": order.metadata["payment_method"],
                "billing_address": order.billing_address,
            }
            async with self._http_session.post(
                f"{self.payment_service_url}/payments/process", json=payload
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    data = await response.json()
                    return {"success": False, "error": data.get("error", "Payment failed")}
        except aiohttp.ClientError as e:
            logger.error(f"Error processing payment: {e}")
            return {"success": False, "error": "Payment service unavailable"}

    async def _process_refund(self, order: Order) -> None:
        """Process refund via payment service."""
        try:
            payload = {
                "order_id": order.id,
                "amount": order.total_amount,
                "reason": order.metadata.get("cancellation_reason", "Order cancelled"),
            }
            async with self._http_session.post(
                f"{self.payment_service_url}/payments/refund", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to process refund for order {order.id}")
        except aiohttp.ClientError as e:
            logger.error(f"Error processing refund: {e}")

    async def _save_order_to_db(self, conn: asyncpg.Connection, order: Order) -> None:
        """Save order to database."""
        await conn.execute(
            """
            INSERT INTO orders (id, user_id, status, payment_status, items, total_amount, 
                              shipping_address, billing_address, created_at, updated_at, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
            order.id,
            order.user_id,
            order.status.value,
            order.payment_status.value,
            json.dumps([asdict(item) for item in order.items]),
            order.total_amount,
            json.dumps(order.shipping_address),
            json.dumps(order.billing_address),
            order.created_at,
            order.updated_at,
            json.dumps(order.metadata),
        )

    async def _get_order_from_db(
        self, conn: asyncpg.Connection, order_id: str, user_id: Optional[str] = None
    ) -> Optional[Order]:
        """Get order from database."""
        query = "SELECT * FROM orders WHERE id = $1"
        params = [order_id]

        if user_id:
            query += " AND user_id = $2"
            params.append(user_id)

        row = await conn.fetchrow(query, *params)
        if not row:
            return None

        return self._row_to_order(row)

    async def _get_orders_from_db(
        self,
        conn: asyncpg.Connection,
        user_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Order]:
        """Get orders from database with filtering."""
        query = "SELECT * FROM orders WHERE 1=1"
        params = []
        param_count = 1

        if user_id:
            query += f" AND user_id = ${param_count}"
            params.append(user_id)
            param_count += 1

        if status:
            query += f" AND status = ${param_count}"
            params.append(status.value)
            param_count += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)
        return [self._row_to_order(row) for row in rows]

    async def _update_order_in_db(self, conn: asyncpg.Connection, order: Order) -> None:
        """Update order in database."""
        await conn.execute(
            """
            UPDATE orders 
            SET status = $2, payment_status = $3, items = $4, total_amount = $5,
                shipping_address = $6, billing_address = $7, updated_at = $8, metadata = $9
            WHERE id = $1
        """,
            order.id,
            order.status.value,
            order.payment_status.value,
            json.dumps([asdict(item) for item in order.items]),
            order.total_amount,
            json.dumps(order.shipping_address),
            json.dumps(order.billing_address),
            order.updated_at,
            json.dumps(order.metadata),
        )

    def _row_to_order(self, row: asyncpg.Record) -> Order:
        """Convert database row to Order object."""
        return Order(
            id=row["id"],
            user_id=row["user_id"],
            status=OrderStatus(row["status"]),
            payment_status=PaymentStatus(row["payment_status"]),
            items=[OrderItem(**item) for item in json.loads(row["items"])],
            total_amount=row["total_amount"],
            shipping_address=json.loads(row["shipping_address"]),
            billing_address=json.loads(row["billing_address"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=json.loads(row["metadata"]),
        )

    async def _cache_order(self, order: Order) -> None:
        """Cache order in Redis."""
        try:
            order_data = {
                "id": order.id,
                "user_id": order.user_id,
                "status": order.status.value,
                "payment_status": order.payment_status.value,
                "items": [asdict(item) for item in order.items],
                "total_amount": order.total_amount,
                "shipping_address": order.shipping_address,
                "billing_address": order.billing_address,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                "metadata": order.metadata,
            }
            await self._redis.setex(f"order:{order.id}", 3600, json.dumps(order_data))  # 1 hour TTL
        except Exception as e:
            logger.warning(f"Failed to cache order {order.id}: {e}")

    async def _get_cached_order(self, order_id: str) -> Optional[Order]:
        """Get order from cache."""
        try:
            cached_data = await self._redis.get(f"order:{order_id}")
            if not cached_data:
                return None

            data = json.loads(cached_data)
            return Order(
                id=data["id"],
                user_id=data["user_id"],
                status=OrderStatus(data["status"]),
                payment_status=PaymentStatus(data["payment_status"]),
                items=[OrderItem(**item) for item in data["items"]],
                total_amount=data["total_amount"],
                shipping_address=data["shipping_address"],
                billing_address=data["billing_address"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                metadata=data["metadata"],
            )
        except Exception as e:
            logger.warning(f"Failed to get cached order {order_id}: {e}")
            return None

    def _is_valid_status_transition(self, current: OrderStatus, new: OrderStatus) -> bool:
        """Validate order status transition."""
        valid_transitions = {
            OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
            OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED],
            OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED],
            OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
            OrderStatus.DELIVERED: [],
            OrderStatus.CANCELLED: [],
        }
        return new in valid_transitions.get(current, [])

    async def _send_order_notifications(self, order: Order) -> None:
        """Send order creation notifications."""
        try:
            payload = {
                "type": "order_created",
                "user_id": order.user_id,
                "order_id": order.id,
                "data": {
                    "status": order.status.value,
                    "total_amount": order.total_amount,
                    "item_count": len(order.items),
                },
            }
            async with self._http_session.post(
                f"{self.notification_service_url}/notifications/send", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to send order notification: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error sending order notification: {e}")

    async def _send_status_notification(self, order: Order) -> None:
        """Send order status change notification."""
        try:
            payload = {
                "type": "order_status_changed",
                "user_id": order.user_id,
                "order_id": order.id,
                "data": {"status": order.status.value, "updated_at": order.updated_at.isoformat()},
            }
            async with self._http_session.post(
                f"{self.notification_service_url}/notifications/send", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to send status notification: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error sending status notification: {e}")

    async def _send_cancellation_notification(self, order: Order) -> None:
        """Send order cancellation notification."""
        try:
            payload = {
                "type": "order_cancelled",
                "user_id": order.user_id,
                "order_id": order.id,
                "data": {
                    "reason": order.metadata.get("cancellation_reason", "Order cancelled"),
                    "refund_amount": (
                        order.total_amount if order.payment_status == PaymentStatus.COMPLETED else 0
                    ),
                },
            }
            async with self._http_session.post(
                f"{self.notification_service_url}/notifications/send", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to send cancellation notification: {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error sending cancellation notification: {e}")


# Example usage and testing
async def main():
    """Example usage of the OrderService."""
    db_config = {
        "host": "localhost",
        "port": 5432,
        "database": "orders_db",
        "user": "postgres",
        "password": "password",
    }

    redis_config = {"host": "localhost", "port": 6379}

    service = OrderService(db_config, redis_config)

    try:
        await service.initialize()

        # Example: Create an order
        order_data = OrderCreateRequest(
            user_id="user123",
            items=[
                {
                    "product_id": "prod1",
                    "product_name": "Laptop",
                    "quantity": 1,
                    "unit_price": 999.99,
                    "total_price": 999.99,
                }
            ],
            shipping_address={
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip": "12345",
                "country": "US",
            },
            billing_address={
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip": "12345",
                "country": "US",
            },
            payment_method="credit_card",
        )

        order = await service.create_order(order_data)
        print(f"Created order: {order.id}")

        # Example: Get order
        retrieved_order = await service.get_order(order.id)
        print(f"Retrieved order: {retrieved_order.id if retrieved_order else 'Not found'}")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
