"""
Django Views for E-commerce Application
======================================

This module contains the view logic for the e-commerce application,
demonstrating complex business logic that benefits from understanding tools.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, F
import logging

from .models import Product, Category, Cart, CartItem, Order, OrderItem
from .forms import AddToCartForm, CheckoutForm

logger = logging.getLogger(__name__)


def product_list(request):
    """Display paginated list of products with filtering."""
    products = Product.objects.filter(is_active=True).select_related("category")

    # Search functionality
    search_query = request.GET.get("search")
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Category filtering
    category_id = request.GET.get("category")
    if category_id:
        products = products.filter(category_id=category_id)

    # Price range filtering
    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Pagination
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Category.objects.all()

    context = {
        "page_obj": page_obj,
        "categories": categories,
        "search_query": search_query,
        "selected_category": category_id,
        "min_price": min_price,
        "max_price": max_price,
    }

    return render(request, "ecommerce/product_list.html", context)


def product_detail(request, product_id):
    """Display detailed product information."""
    product = get_object_or_404(Product, id=product_id, is_active=True)

    # Get related products from same category
    related_products = Product.objects.filter(category=product.category, is_active=True).exclude(
        id=product_id
    )[:4]

    # Check if product is in user's cart
    in_cart = False
    if request.user.is_authenticated:
        try:
            cart = request.user.cart
            in_cart = cart.items.filter(product=product).exists()
        except Cart.DoesNotExist:
            pass

    context = {
        "product": product,
        "related_products": related_products,
        "in_cart": in_cart,
    }

    return render(request, "ecommerce/product_detail.html", context)


@login_required
def add_to_cart(request, product_id):
    """Add product to user's cart with validation."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    product = get_object_or_404(Product, id=product_id, is_active=True)
    form = AddToCartForm(request.POST)

    if not form.is_valid():
        return JsonResponse({"error": "Invalid form data"}, status=400)

    quantity = form.cleaned_data["quantity"]

    # Validate stock availability
    if not product.is_in_stock():
        return JsonResponse({"error": "Product is out of stock"}, status=400)

    if quantity > product.stock_quantity:
        return JsonResponse({"error": f"Only {product.stock_quantity} items available"}, status=400)

    try:
        # Get or create cart for user
        cart, created = Cart.objects.get_or_create(user=request.user)

        # Add item to cart
        cart_item = cart.add_item(product, quantity)

        logger.info(f"Added {quantity} of {product.name} to cart for user {request.user.username}")

        return JsonResponse(
            {
                "success": True,
                "message": f"Added {quantity} {product.name} to cart",
                "cart_total": cart.get_total(),
                "cart_items_count": cart.items.count(),
            }
        )

    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return JsonResponse({"error": "Failed to add item to cart"}, status=500)


@login_required
def cart_view(request):
    """Display user's shopping cart."""
    try:
        cart = request.user.cart
        cart_items = cart.items.select_related("product").all()
    except Cart.DoesNotExist:
        cart = None
        cart_items = []

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "total": cart.get_total() if cart else 0,
    }

    return render(request, "ecommerce/cart.html", context)


@login_required
def update_cart_item(request, item_id):
    """Update quantity of cart item."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    new_quantity = int(request.POST.get("quantity", 1))

    if new_quantity <= 0:
        cart_item.delete()
        return JsonResponse({"success": True, "message": "Item removed from cart"})

    if new_quantity > cart_item.product.stock_quantity:
        return JsonResponse(
            {"error": f"Only {cart_item.product.stock_quantity} items available"}, status=400
        )

    cart_item.quantity = new_quantity
    cart_item.save()

    return JsonResponse(
        {
            "success": True,
            "message": "Cart updated",
            "subtotal": cart_item.get_subtotal(),
            "cart_total": cart_item.cart.get_total(),
        }
    )


@login_required
@transaction.atomic
def checkout(request):
    """Process order checkout with inventory management."""
    try:
        cart = request.user.cart
        cart_items = cart.items.select_related("product").all()
    except Cart.DoesNotExist:
        messages.error(request, "Your cart is empty")
        return redirect("cart")

    if not cart_items:
        messages.error(request, "Your cart is empty")
        return redirect("cart")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                # Validate stock availability for all items
                for item in cart_items:
                    if not item.product.is_in_stock():
                        messages.error(request, f"{item.product.name} is out of stock")
                        return render(request, "ecommerce/checkout.html", {"form": form})

                    if item.quantity > item.product.stock_quantity:
                        messages.error(
                            request,
                            f"Only {item.product.stock_quantity} {item.product.name} available",
                        )
                        return render(request, "ecommerce/checkout.html", {"form": form})

                # Create order
                order = Order.objects.create(
                    user=request.user,
                    total_amount=cart.get_total(),
                    shipping_address=form.cleaned_data["shipping_address"],
                )

                # Create order items and reduce stock
                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        quantity=item.quantity,
                        price_at_time=item.product.price,
                    )
                    item.product.reduce_stock(item.quantity)

                # Process the order
                order.process_order()

                # Clear the cart
                cart.items.all().delete()

                logger.info(f"Order {order.id} created for user {request.user.username}")
                messages.success(request, f"Order #{order.id} placed successfully!")
                return redirect("order_detail", order_id=order.id)

            except Exception as e:
                logger.error(f"Checkout error: {str(e)}")
                messages.error(request, "An error occurred during checkout. Please try again.")

    else:
        form = CheckoutForm()

    context = {
        "form": form,
        "cart_items": cart_items,
        "total": cart.get_total(),
    }

    return render(request, "ecommerce/checkout.html", context)


@login_required
def order_detail(request, order_id):
    """Display order details."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.select_related("product").all()

    context = {
        "order": order,
        "order_items": order_items,
    }

    return render(request, "ecommerce/order_detail.html", context)


@login_required
def order_history(request):
    """Display user's order history."""
    orders = Order.objects.filter(user=request.user).order_by("-created_at")

    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
    }

    return render(request, "ecommerce/order_history.html", context)
