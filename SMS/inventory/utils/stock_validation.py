def validate_stock_change(batch, quantity, action):
    """
    action: 'ADD' | 'REMOVE'
    """

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    if hasattr(batch, "is_active") and not batch.is_active:
        raise ValueError("Inactive batch cannot be adjusted")

    if action == "REMOVE":
        if batch.quantity < quantity:
            raise ValueError(
                f"Insufficient stock. Available: {batch.quantity}"
            )

#  LOW STOCK COMMON LOGIC

from inventory.models import Product
from django.db.models import F



#  LOW STOCK COMMON LOGIC


def get_low_stock_queryset(company):
    """
    Low Stock = stock_quantity <= low_stock_limit
    Single source of truth for Dashboard & Inventory
    """
    return Product.objects.filter(
        company=company,
        stock_quantity__lte=F('low_stock_limit')
    )