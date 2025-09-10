"""
Django E-commerce Example
========================

This example demonstrates Understand-First with a Django e-commerce application.
It shows how the tool handles Django models, views, and complex business logic.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Category(models.Model):
    """Product categories for organizing items."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Product model with inventory management."""

    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def is_in_stock(self):
        """Check if product has available stock."""
        return self.stock_quantity > 0

    def reduce_stock(self, quantity):
        """Reduce stock quantity, ensuring it doesn't go negative."""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if quantity > self.stock_quantity:
            raise ValueError("Insufficient stock")
        self.stock_quantity -= quantity
        self.save()


class Cart(models.Model):
    """Shopping cart for a user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.username}"

    def get_total(self):
        """Calculate total cart value."""
        return sum(item.get_subtotal() for item in self.items.all())

    def add_item(self, product, quantity=1):
        """Add item to cart or update quantity."""
        item, created = CartItem.objects.get_or_create(
            cart=self, product=product, defaults={"quantity": quantity}
        )
        if not created:
            item.quantity += quantity
            item.save()
        return item


class CartItem(models.Model):
    """Individual items in a shopping cart."""

    cart = models.ForeignKey(Cart, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["cart", "product"]

    def get_subtotal(self):
        """Calculate subtotal for this item."""
        return self.product.price * self.quantity


class Order(models.Model):
    """Order model representing a completed purchase."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"

    def can_be_cancelled(self):
        """Check if order can still be cancelled."""
        return self.status in ["pending", "processing"]

    def process_order(self):
        """Process the order and update inventory."""
        if self.status != "pending":
            raise ValueError("Order is not in pending status")

        # Reduce stock for all items
        for item in self.items.all():
            item.product.reduce_stock(item.quantity)

        self.status = "processing"
        self.save()


class OrderItem(models.Model):
    """Items within an order."""

    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)

    def get_subtotal(self):
        """Calculate subtotal for this order item."""
        return self.price_at_time * self.quantity
