"""
FastAPI E-commerce Example
=========================

This example demonstrates Understand-First with a FastAPI e-commerce application.
It shows how the tool handles modern async Python patterns, dependency injection,
and API design best practices.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import logging
import hashlib
import secrets
import json
from decimal import Decimal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="E-commerce API",
    description="A modern e-commerce API built with FastAPI",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# In-memory storage (in production, use a real database)
users_db: Dict[str, Dict] = {}
products_db: Dict[str, Dict] = {}
orders_db: Dict[str, Dict] = {}
carts_db: Dict[str, Dict] = {}


# Pydantic models
class UserCreate(BaseModel):
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
    id: str
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    is_active: bool


class ProductCreate(BaseModel):
    name: str
    description: str
    price: Decimal
    category: str
    stock_quantity: int = 0


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: Decimal
    category: str
    stock_quantity: int
    is_active: bool
    created_at: datetime


class CartItemCreate(BaseModel):
    product_id: str
    quantity: int

    @validator("quantity")
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError("Quantity must be positive")
        return v


class OrderCreate(BaseModel):
    shipping_address: str
    payment_method: str


class OrderResponse(BaseModel):
    id: str
    user_id: str
    status: str
    total_amount: Decimal
    shipping_address: str
    created_at: datetime
    items: List[Dict[str, Any]]


# Authentication utilities
def hash_password(password: str) -> str:
    """Hash password using secure method."""
    salt = secrets.token_hex(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    )
    return f"{salt}:{password_hash.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against hash."""
    try:
        salt, hash_part = hashed.split(":")
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
        )
        return password_hash.hex() == hash_part
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    """Create a simple access token (in production, use JWT)."""
    return f"token_{user_id}_{secrets.token_urlsafe(16)}"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Get current user from token."""
    token = credentials.credentials
    if not token.startswith("token_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        )

    # Extract user ID from token (simplified)
    try:
        user_id = token.split("_")[1]
        if user_id not in users_db:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return users_db[user_id]
    except (IndexError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")


# Business logic services
class UserService:
    """Service for user management operations."""

    @staticmethod
    async def create_user(user_data: UserCreate) -> UserResponse:
        """Create a new user."""
        # Check if user already exists
        for user in users_db.values():
            if user["email"] == user_data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User with this email already exists",
                )

        # Create user
        user_id = secrets.token_urlsafe(16)
        hashed_password = hash_password(user_data.password)

        user = {
            "id": user_id,
            "email": user_data.email,
            "password_hash": hashed_password,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "created_at": datetime.utcnow(),
            "is_active": True,
        }

        users_db[user_id] = user
        logger.info(f"Created user {user_id} with email {user_data.email}")

        return UserResponse(
            id=user_id,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            created_at=user["created_at"],
            is_active=True,
        )

    @staticmethod
    async def authenticate_user(email: str, password: str) -> Optional[str]:
        """Authenticate user and return access token."""
        for user in users_db.values():
            if user["email"] == email and verify_password(password, user["password_hash"]):
                return create_access_token(user["id"])
        return None


class ProductService:
    """Service for product management operations."""

    @staticmethod
    async def create_product(product_data: ProductCreate) -> ProductResponse:
        """Create a new product."""
        product_id = secrets.token_urlsafe(16)

        product = {
            "id": product_id,
            "name": product_data.name,
            "description": product_data.description,
            "price": product_data.price,
            "category": product_data.category,
            "stock_quantity": product_data.stock_quantity,
            "is_active": True,
            "created_at": datetime.utcnow(),
        }

        products_db[product_id] = product
        logger.info(f"Created product {product_id}: {product_data.name}")

        return ProductResponse(**product)

    @staticmethod
    async def get_products(
        category: Optional[str] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ProductResponse]:
        """Get products with filtering and pagination."""
        products = list(products_db.values())

        # Apply filters
        if category:
            products = [p for p in products if p["category"] == category]
        if min_price is not None:
            products = [p for p in products if p["price"] >= min_price]
        if max_price is not None:
            products = [p for p in products if p["price"] <= max_price]

        # Apply pagination
        products = products[offset : offset + limit]

        return [ProductResponse(**p) for p in products]

    @staticmethod
    async def update_stock(product_id: str, quantity_change: int) -> bool:
        """Update product stock quantity."""
        if product_id not in products_db:
            return False

        product = products_db[product_id]
        new_quantity = product["stock_quantity"] + quantity_change

        if new_quantity < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock"
            )

        product["stock_quantity"] = new_quantity
        logger.info(f"Updated stock for product {product_id}: {new_quantity}")
        return True


class CartService:
    """Service for shopping cart operations."""

    @staticmethod
    async def add_to_cart(user_id: str, item_data: CartItemCreate) -> Dict[str, Any]:
        """Add item to user's cart."""
        # Verify product exists and has stock
        if item_data.product_id not in products_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        product = products_db[item_data.product_id]
        if product["stock_quantity"] < item_data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient stock"
            )

        # Get or create cart
        if user_id not in carts_db:
            carts_db[user_id] = {"items": {}, "created_at": datetime.utcnow()}

        cart = carts_db[user_id]

        # Add or update item
        if item_data.product_id in cart["items"]:
            cart["items"][item_data.product_id]["quantity"] += item_data.quantity
        else:
            cart["items"][item_data.product_id] = {
                "product": product,
                "quantity": item_data.quantity,
                "added_at": datetime.utcnow(),
            }

        logger.info(
            f"Added {item_data.quantity} of product {item_data.product_id} to cart for user {user_id}"
        )

        return {
            "message": "Item added to cart",
            "cart_total": CartService.calculate_cart_total(cart),
            "item_count": sum(item["quantity"] for item in cart["items"].values()),
        }

    @staticmethod
    def calculate_cart_total(cart: Dict[str, Any]) -> Decimal:
        """Calculate total cart value."""
        total = Decimal("0")
        for item in cart["items"].values():
            total += item["product"]["price"] * item["quantity"]
        return total


class OrderService:
    """Service for order management operations."""

    @staticmethod
    async def create_order(user_id: str, order_data: OrderCreate) -> OrderResponse:
        """Create a new order from user's cart."""
        if user_id not in carts_db or not carts_db[user_id]["items"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

        cart = carts_db[user_id]

        # Validate stock availability
        for product_id, item in cart["items"].items():
            if products_db[product_id]["stock_quantity"] < item["quantity"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for product {products_db[product_id]['name']}",
                )

        # Create order
        order_id = secrets.token_urlsafe(16)
        total_amount = CartService.calculate_cart_total(cart)

        order = {
            "id": order_id,
            "user_id": user_id,
            "status": "pending",
            "total_amount": total_amount,
            "shipping_address": order_data.shipping_address,
            "created_at": datetime.utcnow(),
            "items": [],
        }

        # Create order items and update stock
        for product_id, item in cart["items"].items():
            order["items"].append(
                {
                    "product_id": product_id,
                    "product_name": item["product"]["name"],
                    "quantity": item["quantity"],
                    "price": item["product"]["price"],
                }
            )

            # Update stock
            await ProductService.update_stock(product_id, -item["quantity"])

        orders_db[order_id] = order

        # Clear cart
        carts_db[user_id] = {"items": {}, "created_at": datetime.utcnow()}

        logger.info(f"Created order {order_id} for user {user_id} with total {total_amount}")

        return OrderResponse(**order)


# API Routes
@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register a new user."""
    return await UserService.create_user(user_data)


@app.post("/auth/login")
async def login(email: str, password: str):
    """Login user and get access token."""
    token = await UserService.authenticate_user(email, password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return {"access_token": token, "token_type": "bearer"}


@app.get("/products", response_model=List[ProductResponse])
async def get_products(
    category: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Get products with filtering and pagination."""
    return await ProductService.get_products(category, min_price, max_price, limit, offset)


@app.post("/products", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new product (admin only)."""
    return await ProductService.create_product(product_data)


@app.post("/cart/add")
async def add_to_cart(
    item_data: CartItemCreate, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Add item to cart."""
    return await CartService.add_to_cart(current_user["id"], item_data)


@app.get("/cart")
async def get_cart(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user's cart."""
    user_id = current_user["id"]
    if user_id not in carts_db:
        return {"items": [], "total": 0, "item_count": 0}

    cart = carts_db[user_id]
    return {
        "items": list(cart["items"].values()),
        "total": CartService.calculate_cart_total(cart),
        "item_count": sum(item["quantity"] for item in cart["items"].values()),
    }


@app.post("/orders", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new order."""
    return await OrderService.create_order(current_user["id"], order_data)


@app.get("/orders", response_model=List[OrderResponse])
async def get_orders(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get user's orders."""
    user_orders = [order for order in orders_db.values() if order["user_id"] == current_user["id"]]
    return [OrderResponse(**order) for order in user_orders]


@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get specific order."""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]
    if order["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return OrderResponse(**order)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow(), "version": "1.0.0"}


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the application."""
    logger.info("Starting FastAPI e-commerce application")

    # Create some sample products
    sample_products = [
        ProductCreate(
            name="Laptop Pro",
            description="High-performance laptop for professionals",
            price=Decimal("1299.99"),
            category="Electronics",
            stock_quantity=10,
        ),
        ProductCreate(
            name="Wireless Headphones",
            description="Noise-cancelling wireless headphones",
            price=Decimal("199.99"),
            category="Electronics",
            stock_quantity=25,
        ),
        ProductCreate(
            name="Coffee Maker",
            description="Automatic coffee maker with timer",
            price=Decimal("89.99"),
            category="Appliances",
            stock_quantity=15,
        ),
    ]

    for product_data in sample_products:
        await ProductService.create_product(product_data)

    logger.info("Sample products created")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
