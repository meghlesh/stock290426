from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from accounts.models import UserProfile
from inventory.utils.stock_validation import validate_stock_change
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.decorators import method_decorator
from django.db import models  
from django.db.models import Max, Sum, Count, Q, F, Value, Case, When  
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import timedelta, date
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from accounts.models import UserProfile
from .models import Product, Category, Vendor, StockTransaction, ProductBatch, SalesOrderItem
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import json
from django.views.decorators.http import require_POST
import qrcode
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from math import ceil
from django.db import transaction, DataError
from decimal import Decimal, InvalidOperation
from django.db.models import ProtectedError
from django.core.paginator import Paginator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from reportlab.lib.enums import TA_LEFT
from django.db.models import Sum, F
from django.db.models.functions import TruncDay, TruncMonth
from django.utils.dateparse import parse_date
from .models import PurchaseOrderItem
from django.db.models import F
from django.db.models import Sum, Avg, Count, F, Value, DecimalField, IntegerField
from django.db.models.functions import Coalesce
import base64
from io import BytesIO
from django.shortcuts import render, get_object_or_404
import re
from django.shortcuts import render, redirect
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .models import PurchaseOrder
from openpyxl.styles import Font
from .models import Product, Category, SalesOrder, PurchaseOrder, PurchaseOrderItem, Vendor, StockTransaction, ProductBatch, SalesOrderItem
from django.contrib import messages
from datetime import date, timedelta
from django.db.models import Sum, Min
from django.shortcuts import render
from django.utils import timezone
from collections import defaultdict
from inventory.models import ProductBatch, StockTransaction, PurchaseOrder
import json
from django.db.models import Q
from django.db.models import Case, When, IntegerField
import uuid
from datetime import date
import csv
from django.http import HttpResponse
from django.http import JsonResponse
from decimal import Decimal
from django.shortcuts import render, redirect
from .models import Quote
from .forms import QuoteForm, QuoteItemFormSet
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from accounts.models import UserProfile
from .models import Vendor
from django.db.models import Sum
from django.utils.timezone import now
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import UserProfile
from .models import SalesOrder, PurchaseOrder
from django.http import HttpResponse
import openpyxl
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from accounts.models import UserProfile
from .models import SalesOrder
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import CustomerForm, AddressForm, ContactPersonForm
from accounts.models import UserProfile
from .models import Product
from django.http import HttpResponse
from openpyxl import Workbook
from .models import Customer, Address, ContactPerson
from .forms import ProductForm
from django.db import transaction
from django.db import IntegrityError
from django.forms import inlineformset_factory, modelformset_factory
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q
import json
from datetime import date, timedelta
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime
from django.urls import reverse
from django.shortcuts import redirect

from .views_expiry_reports import (
    NearExpiryProductsReportAPIView,
    ExpiredStockReportAPIView,
    FEFOComplianceReportAPIView,
    BlockedExpiredSalesReportAPIView,
    LossDueToExpiryReportAPIView,
    ExpirySummaryDashboardAPIView
)
from .views_sales_reports import (
    SalesPeriodicReportAPIView,
    ProductWiseSalesReportAPIView,
    CategoryWiseSalesReportAPIView,
    BatchWiseSalesReportAPIView,
    RefundReturnReportAPIView,
    MarginReportAPIView,
    SalesDashboardSummaryAPIView
)
from .views_dashboard_reports import (
    DashboardKPIsAPIView,
    SalesTrendsChartAPIView,
    StockMovementTrendsChartAPIView,
    CategoryContributionChartAPIView,
    RoleBasedDashboardAPIView,
    DashboardWidgetAPIView
)
from inventory.utils.stock_validation import (
    validate_stock_change,
    get_low_stock_queryset
)


#  COMMON CHECK
def owner_required(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    if profile.role != "COMPANY_OWNER":
        return None
    return profile.company

def get_item_unit_price(item):
    for key in ("unit_price", "price", "rate", "selling_price", "unit_cost"):
        if hasattr(item, key) and getattr(item, key) is not None:
            return getattr(item, key)

    product = getattr(item, "product", None)
    if product:
        for key in ("unit_price", "price", "selling_price", "mrp", "sale_price"):
            if hasattr(product, key) and getattr(product, key) is not None:
                return getattr(product, key)

    return 0



@login_required
def product_list(request):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    LOW_STOCK_LIMIT = 5
    today = date.today()
    near_limit = today + timedelta(days=30)

    #  Latest added products show first
    products = Product.objects.filter(
        company=company
    ).order_by('-id')

    filter_type = request.GET.get("filter")

    if filter_type == "low_stock":
        products = products.filter(
            stock_quantity__gt=0,
            stock_quantity__lte=LOW_STOCK_LIMIT
        )

    #  Search
    search_query = request.GET.get("q", "").strip()

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(sku__icontains=search_query)
        )

    #  Category filter
    category_id = request.GET.get("category", "")
    if category_id:
        if category_id == "uncategorized":
            products = products.filter(
                category__isnull=True
            )
        else:
            products = products.filter(
                category_id=category_id
            )

    categories = Category.objects.filter(
        company=company
    )

    product_data = []
    low_stock_count = 0

    for p in products:

        all_batches = ProductBatch.objects.filter(
            company=company,
            product=p,
            is_active=True
        )

        #  TOTAL stock (audit only)
        total_stock = all_batches.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        #  SELLABLE stock
        active_batches = all_batches.filter(
            Q(expiry_date__gte=today) |
            Q(expiry_date__isnull=True),
            quantity__gt=0
        )

        sellable_stock = active_batches.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        # Stock status
        if sellable_stock == 0:
            stock_status = "out_of_stock"
        elif 1 <= sellable_stock <= LOW_STOCK_LIMIT:
            stock_status = "low_stock"
            low_stock_count += 1
        else:
            stock_status = "in_stock"

        # Apply low stock filter correctly
        if (
            filter_type == "low_stock"
            and stock_status != "low_stock"
        ):
            continue

        has_near_expiry = active_batches.filter(
            expiry_date__range=[today, near_limit]
        ).exists()

        is_fully_expired = (
            sellable_stock == 0 and total_stock > 0
        )

        product_data.append({
            "product": p,
            "batch_stock": sellable_stock,
            "total_stock": total_stock,
            "has_near_expiry": has_near_expiry,
            "is_fully_expired": is_fully_expired,
            "is_low_stock": stock_status == "low_stock",
            "is_out_of_stock": stock_status == "out_of_stock",
            "is_in_stock": stock_status == "in_stock",
        })

    paginator = Paginator(
        product_data,
        10
    )

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(
        page_number
    )

    total_products_count = len(
        product_data
    )

    context = {
        "product_data": page_obj,
        "categories": categories,
        "search_query": search_query,
        "selected_category": category_id,
        "company": company,
        "LOW_STOCK_LIMIT": LOW_STOCK_LIMIT,
        "low_stock_count": low_stock_count,
        "products": products,
        "page_obj": page_obj,
        "active_filter": filter_type,
        "total_products_count": total_products_count,
    }

    return render(
        request,
        "inventory/product_list.html",
        context
    )


@login_required
def add_product(request):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    categories = Category.objects.filter(company=company)

    if request.method == 'POST':
        form = ProductForm(request.POST, company=company)

        if form.is_valid():
            product = form.save(commit=False)
            product.company = company

            # Get stock from form
            initial_stock = form.cleaned_data.get("stock_quantity", 0)

            product.stock_quantity = 0  # keep consistent (batch-based system)
            product.save()

            #  CREATE BATCH (MAIN FIX)
            expiry_date = request.POST.get('default_expiry_date')
            if initial_stock > 0:
                ProductBatch.objects.create(
                    company=company,
                    product=product,
                    batch_number="INITIAL-STOCK",
                    expiry_date=expiry_date if expiry_date else None,  # or form field if exists
                    quantity=initial_stock,
                    is_active=True
                )

            # Optional: keep system consistent
            reconcile_product_stock(company)

            messages.success(request, 'Product created successfully!')
            return redirect('add_product')

    else:
        form = ProductForm(company=company)

    return render(request, 'inventory/add_product.html', {
        'form': form,
        'categories': categories,
        'company': company
    })




def edit_product(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    product = get_object_or_404(Product, pk=pk, company=company)
    categories = Category.objects.filter(company=company)

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product, company=company)

        if form.is_valid():
            product = form.save(commit=False)

            new_stock = form.cleaned_data.get("stock_quantity", 0)

            #  OLD SELLABLE STOCK (from batches)
            today = date.today()
            old_stock = (
                ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=today,
                    quantity__gt=0,
                    is_active=True
                )
                .aggregate(total=Sum("quantity"))["total"] or 0
            )

            diff = new_stock - old_stock

            #  Save product fields (NOT stock)
            product.save(update_fields=[
                "name",
                "sku",
                "category",
                "purchase_price",
                "selling_price",
                "is_expiry_tracked",
            ])

            #  MAIN FIX: update batch stock
            if diff != 0:
                batch, _ = ProductBatch.objects.get_or_create(
                    company=company,
                    product=product,
                    batch_number="MANUAL-EDIT",
                    defaults={
                        "expiry_date": None,
                        "quantity": 0,
                        "is_active": True,
                    },
                )

                batch.quantity += diff
                batch.save(update_fields=["quantity"])

            #  Final consistency
            reconcile_product_stock(company)

            messages.success(request, "Product updated successfully!")
            return redirect("product_list")

    else:
        form = ProductForm(instance=product, company=company)

    return render(request, "inventory/edit_product.html", {
        "form": form,
        "product": product,
        "categories": categories,
        "company": company
    })




@login_required
def delete_product(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    product = get_object_or_404(Product, pk=pk, company=company)

    if request.method == "POST":
        product.delete()
        messages.error(request, "Product deleted successfully")
        return redirect("product_list")

    return redirect("product_list")




@login_required
def category_list(request):
    company = owner_required(request)
    if not company:
        return redirect("company_login")
   
        

    categories = Category.objects.filter(company=company)

    if request.method == "POST":
        name = re.sub(r'\s+', ' ', request.POST.get("name", "").strip())
        if not name:
            messages.error(request, "Category name cannot be empty or spaces only")
            return redirect("category_list")
           
        if Category.objects.filter(company=company, name__iexact=name).exists():
                messages.error(request, "Category already exists")
                return redirect("category_list")
        
        Category.objects.create(company=company, name=name)
        messages.success(request, "Category added successfully")
        return redirect("category_list")


    return render(request, "inventory/category_list.html", {
        "categories": categories,
        "company": company,
    })


#  EDIT CATEGORY
@login_required
def edit_category(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    category = get_object_or_404(Category, pk=pk, company=company)

    if request.method == "POST":
        category.name = request.POST.get("name")
        category.save()
        messages.success(request, "Category updated successfully")
        return redirect("category_list")

    return render(request, "inventory/edit_category.html", {
        "category": category,
        "company": company,
    })


@login_required
def delete_category(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    category = get_object_or_404(Category, pk=pk, company=company)
    Product.objects.filter(company=company, category=category).update(category=None)

    if request.method == "POST":
        Product.objects.filter(company=company, category=category).update(category=None)
        category.delete()
        messages.error(request, "Category deleted successfully")

    return redirect("category_list")

@login_required
def sales_order_list(request):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    # 1. BASE QUERY
    orders_queryset = SalesOrder.objects.filter(company=company).annotate(
    quantity=Coalesce(Sum('items__quantity'), Value(0))
)


    # 2. SEARCH FILTER
    search_query = request.GET.get("customer")
    if search_query:
        orders_queryset = orders_queryset.filter(
            Q(customer_name__icontains=search_query) |
            Q(order_number__icontains=search_query)
        )

    status_filter = request.GET.get("status")

    if status_filter:
        if status_filter.upper() == "PENDING":
            orders_queryset = orders_queryset.filter(
                status__icontains="pending"
            )
        else:
            orders_queryset = orders_queryset.filter(
                status__iexact=status_filter
            )

    active_filter = None
    if status_filter:
        if status_filter.upper() == "PENDING":
            active_filter = "Pending"
        else:
            active_filter = status_filter.title()

    # 4. METRICS
    total_orders = orders_queryset.count()

    pending_orders = orders_queryset.filter(
        status__icontains="pending"
    ).count()

    completed_orders = orders_queryset.filter(
        status__in=["DELIVERED", "COMPLETED", "SHIPPED"]
    ).count()

    revenue = orders_queryset.filter(
        status__in=["DELIVERED", "COMPLETED"]
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    # 5. PAGINATION
    orders_queryset = orders_queryset.order_by("-created_at")

    paginator = Paginator(orders_queryset, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 6. RESPONSE
    return render(
        request,
        "inventory/sales_order_list.html",
        {
            "orders": page_obj,
            "page_obj": page_obj,
            "company": company,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "revenue": revenue,
            "selected_status": status_filter,
            "active_filter": active_filter,  
        }
    )




@login_required
@transaction.atomic
def add_sales_order(request):
    profile = request.user.userprofile
    products = Product.objects.filter(company=profile.company)
    today = timezone.now().date()

    warning_near_expiry = ProductBatch.objects.filter(
        company=profile.company,
        expiry_date__range=[today, today + timedelta(days=30)],
        quantity__gt=0,
        is_active=True
    ).exists()

    if request.method == "POST":
        customer_name = request.POST.get("customer_name", "").strip()

        #  MULTI-ITEM INPUTS
        product_ids = request.POST.getlist("product[]")
        quantities = request.POST.getlist("quantity[]")

        
        #  VALIDATION
        
        if not customer_name:
            messages.error(request, "Customer name is required.")
            return redirect("add_sales_order")

        if len(customer_name) > 50:
            messages.error(request, "Customer name cannot exceed 50 characters.")
            return redirect("add_sales_order")

        if not product_ids:
            messages.error(request, "Add at least one product.")
            return redirect("add_sales_order")

        order_items_data = []
        total_amount = 0

        
        #  LOOP THROUGH ITEMS
        
        for i in range(len(product_ids)):
            try:
                product_id = product_ids[i]

                #  ADD THIS BLOCK (VERY IMPORTANT)
                if not product_id or product_id == "undefined":
                    messages.error(request, "Please select a valid product.")
                    return redirect("add_sales_order")

                product_id = int(product_id)  # force integer

                qty = int(quantities[i])

            except (IndexError, ValueError):
                messages.error(request, "Invalid product data.")
                return redirect("add_sales_order")

            if qty <= 0:
                messages.error(request, "Quantity must be greater than 0.")
                return redirect("add_sales_order")

            product = get_object_or_404(
                Product,
                id=product_id,
                company=profile.company
            )

            # FIX: Accept batches with NO expiry, and order them so Nulls are used LAST
            batches = (
                ProductBatch.objects
                .select_for_update()
                .filter(
                    Q(expiry_date__gte=today) | Q(expiry_date__isnull=True),
                    company=profile.company,
                    product=product,
                    quantity__gt=0,
                    is_active=True
                )
                .order_by(F("expiry_date").asc(nulls_last=True))
            )

            if not batches.exists():
                messages.error(request, f"No stock for {product.name}.")
                return redirect("add_sales_order")

            total_available = sum(b.quantity for b in batches)

            if total_available < qty:
                messages.error(request, f"Insufficient stock for {product.name}.")
                return redirect("add_sales_order")

            order_items_data.append({
                "product": product,
                "quantity": qty,
                "batches": batches
            })

            total_amount += product.selling_price * qty

        
        #  CREATE ORDER
        
        order = SalesOrder.objects.create(
            company=profile.company,
            order_number=f"ORD-{SalesOrder.objects.count() + 1}",
            customer_name=customer_name,
            total_amount=total_amount
        )

        
        #  CREATE ITEMS + FEFO
        
        # If your validate_stock_change throws import error, un-comment it at the top
        from inventory.utils.stock_validation import validate_stock_change

        for item in order_items_data:
            product = item["product"]
            qty = item["quantity"]
            batches = item["batches"]

            SalesOrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=product.selling_price
            )

            remaining_qty = qty

            for batch in batches:
                if remaining_qty <= 0:
                    break

                deduct_qty = min(batch.quantity, remaining_qty)

                validate_stock_change(batch, deduct_qty, "REMOVE")

                batch.quantity -= deduct_qty
                batch.save(update_fields=["quantity"])

                remaining_qty -= deduct_qty

                StockTransaction.objects.create(
                    company=profile.company,
                    product=product,
                    batch=batch,
                    transaction_type="OUT",
                    source="SALE",
                    quantity=deduct_qty,
                    reference_number=order.order_number,
                    created_by=request.user
                )

            #  UPDATE PRODUCT STOCK
            # FIX: Ensure it counts products with No Expiry Date in the updated stock count!
            product.stock_quantity = (
                ProductBatch.objects.filter(
                    Q(expiry_date__gte=today) | Q(expiry_date__isnull=True),
                    company=profile.company,
                    product=product,
                    quantity__gt=0,
                    is_active=True
                ).aggregate(total=Sum("quantity"))["total"] or 0
            )

            product.save(update_fields=["stock_quantity"])

        messages.success(
            request,
            f"Sales order {order.order_number} created successfully."
        )
        return redirect("sales_orders")

    return render(
        request,
        "inventory/add_sales_order.html",
        {
            "products": products,
            "warning_near_expiry": warning_near_expiry,
            "company": profile.company,
        }
    )

    

@login_required
def fefo_preview_api(request):
    profile = UserProfile.objects.get(user=request.user)
    product_id = request.GET.get("product")
    quantity = int(request.GET.get("quantity", 0))

    preview = []
    today = timezone.now().date()

    if product_id and quantity > 0:
        product = get_object_or_404(Product, id=product_id, company=profile.company)

        batches = ProductBatch.objects.filter(
            company=profile.company,
            product=product,
            expiry_date__gte=today,
            quantity__gt=0,
            is_active=True
        ).order_by("expiry_date")

        remaining = quantity
        for batch in batches:
            if remaining <= 0:
                break
            used = min(batch.quantity, remaining)
            preview.append({
                "batch": batch.batch_number,
                "expiry": batch.expiry_date.strftime("%Y-%m-%d"),
                "qty": used
            })
            remaining -= used

    return JsonResponse({"preview": preview})



@login_required
def stock_movement_report(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    transactions_qs = StockTransaction.objects.filter(
        company=company
    )

    #get filter data
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    flow_type = request.GET.get("flow_type")

    #date filter


    if from_date and to_date:
       transactions_qs = transactions_qs.filter(
        created_at__range=[from_date, to_date]
    )

    elif from_date:
      transactions_qs = transactions_qs.filter(
        created_at__gte=from_date
    )

    elif to_date:
      transactions_qs = transactions_qs.filter(
        created_at__lte=to_date
    )

    if flow_type and flow_type != "All":
        transactions_qs = transactions_qs.filter(
        transaction_type=flow_type
    )
    
    # display order results after filtering
    transactions_qs = transactions_qs.order_by('-created_at')


    paginator = Paginator(transactions_qs, 10)  #  10 records per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    
    # Monthly calculation 
    today = timezone.now()
    first_day = today.replace(day=1)

    monthly_stock_in = transactions_qs.filter(
      transaction_type='IN'
      ).aggregate(total=Sum('quantity'))['total'] or 0

    monthly_stock_out = transactions_qs.filter(
      transaction_type='OUT'
      ).aggregate(total=Sum('quantity'))['total'] or 0

    net_velocity = monthly_stock_in - monthly_stock_out
    return render(
        request,
        "company/stock_movement_report.html",
        {
            "transactions": page_obj,  #  keeps your existing for-loop working
            "page_obj": page_obj,      #  for footer text + buttons
            "company": company,
            "monthly_stock_in": monthly_stock_in,
            "monthly_stock_out": monthly_stock_out,
            "net_velocity": net_velocity,
        }
    )

@login_required
def sales_order_detail(request, pk):
    order = SalesOrder.objects.get(id=pk)

    
    items = order.items.all()   

    
    for item in items:
        unit_price = get_item_unit_price(item)
        item.subtotal = item.quantity * unit_price  

    context = {
        'order': order,
        'items': items,
        'company': order.company
    }

    return render(
        request,
        "inventory/sales_order_detail.html",
        context
    )


@login_required
def update_order_status(request, pk):
    profile = UserProfile.objects.get(user=request.user)
    order = get_object_or_404(
        SalesOrder,
        id=pk,
        company=profile.company
    )

    if request.method == "POST":
        new_status = request.POST.get("status")

        #  BLOCK terminal states (NO CHANGE)
        if order.status in ["DELIVERED", "CANCELLED"]:
            messages.error(
                request,
                "This order is in a final state and cannot be modified."
            )
            return redirect("sales_order_detail", pk=pk)


        # NEW CODE
        old_status = order.status  # kept for future audit/logging if needed
        order.status = new_status
        order.save(update_fields=["status"])

        # Semantic messages based on status
        if new_status == "CANCELLED":
            messages.error(request, "Order cancelled successfully.")
            return redirect("cancel_and_reverse_sales_order", pk=pk)
        elif new_status == "DELIVERED":
            messages.success(request, "Order delivered successfully.")
        elif new_status in ["PENDING", "PROCESSING"]:
            messages.success(request, "Status updated successfully.")

    return redirect("sales_order_detail", pk=pk)


@login_required
def vendor_list(request):
    company = owner_required(request)
    vendors = Vendor.objects.filter(company=company)
    
    name = request.GET.get("name")
    email = request.GET.get("email")

    if name:
        vendors = vendors.filter(display_name__icontains=name)

    if email:
        vendors = vendors.filter(email__icontains=email)

    #  PAGINATION
    total_vendors = vendors.count()
    paginator = Paginator(vendors, 10)
    page_number = request.GET.get("page")
    vendors = paginator.get_page(page_number)

    return render(request, "inventory/vendor_list.html", {
        "vendors": vendors,
        "total_vendors": total_vendors,
        "company": company
    })



@login_required
def edit_vendor(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    vendor = get_object_or_404(Vendor, pk=pk, company=company)
    errors = {}

    if request.method == "POST":

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        company_name = request.POST.get("company_name")
        display_name = request.POST.get("display_name")
        gst_number = request.POST.get("gst_number")
        email = request.POST.get("email")
        mobile = request.POST.get("mobile")
        address = request.POST.get("address")
        salutation = request.POST.get("salutation")

        # ---------- FIRST NAME ----------
        if not first_name:
            errors["first_name"] = "First name is required."
        elif len(first_name) > 20:
            errors["first_name"] = "Maximum 20 characters allowed."
        elif not re.match(r'^[A-Za-z]+$', first_name):
            errors["first_name"] = "Only alphabets allowed."

        # ---------- LAST NAME ----------
        if not last_name:
            errors["last_name"] = "Last name is required."
        elif len(last_name) > 20:
            errors["last_name"] = "Maximum 20 characters allowed."
        elif not re.match(r'^[A-Za-z]+$', last_name):
            errors["last_name"] = "Only alphabets allowed."

        # ---------- COMPANY NAME ----------
        if not company_name:
            errors["company_name"] = "Company name is required."
        elif len(company_name) > 50:
            errors["company_name"] = "Maximum 50 characters allowed."

        # ---------- DISPLAY NAME ----------
        if not display_name:
            errors["display_name"] = "Display name is required."
        elif len(display_name) > 50:
            errors["display_name"] = "Maximum 50 characters allowed."

        # ---------- GST ----------
        gst_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'

        if not gst_number:
            errors["gst_number"] = "GST number is required."
        elif not re.match(gst_regex, gst_number):
            errors["gst_number"] = "Invalid GST format."
        elif Vendor.objects.filter(company=company, gst_number=gst_number).exclude(pk=vendor.pk).exists():
            errors["gst_number"] = "Vendor with this GST already exists."

        # ---------- EMAIL ----------
        email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'

        if not email:
            errors["email"] = "Email is required."
        elif not re.match(email_regex, email):
            errors["email"] = "Enter a valid email (no special characters like #, !)."
        elif Vendor.objects.filter(company=company, email=email).exclude(pk=vendor.pk).exists():
            errors["email"] = "Vendor with this email already exists."
        else:
            try:
                validate_email(email)  # extra safety
            except ValidationError:
                errors["email"] = "Enter a valid email address."

        # ---------- MOBILE ----------
        if not mobile:
            errors["mobile"] = "Mobile number is required."
        elif not re.match(r'^[0-9]{10}$', mobile):
            errors["mobile"] = "Enter a valid 10-digit mobile number."
        elif Vendor.objects.filter(company=company, mobile=mobile).exclude(pk=vendor.pk).exists():
            errors["mobile"] = "Vendor with this mobile number already exists."

        # ---------- ADDRESS ----------
        if not address:
            errors["address"] = "Address is required."

        if errors:
            return render(request, "inventory/edit_vendor.html", {
                "vendor": vendor,
                "company": company,
                "errors": errors
            })

        # SAVE
        vendor.salutation = salutation
        vendor.first_name = first_name
        vendor.last_name = last_name
        vendor.company_name = company_name
        vendor.display_name = display_name
        vendor.gst_number = gst_number
        vendor.email = email
        vendor.mobile = mobile
        vendor.address = address

        vendor.save()

        messages.success(request, "Vendor updated successfully.")
        return redirect("vendor_list")

    return render(request, "inventory/edit_vendor.html", {
        "company": company,
        "vendor": vendor,
        "errors": {}
    })


@login_required
def delete_vendor(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    vendor = get_object_or_404(Vendor, pk=pk, company=company)

    if request.method == "POST":
        try:
            vendor_name = vendor.display_name  # optional (better message)
            vendor.delete()

            messages.error(request, f"{vendor_name} deleted successfully.")  

        except ProtectedError:
            messages.error(
                request,
                "Cannot delete this vendor because it is used in Purchase Orders."
            )

    return redirect("vendor_list")



@login_required
def export_vendors_csv(request):
    profile = UserProfile.objects.get(user=request.user)
    vendors = Vendor.objects.filter(company=profile.company)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="vendors.csv"'

    writer = csv.writer(response)
    writer.writerow(["Vendor Name", "Company Name", "Email", "Mobile"])

    for v in vendors:
        writer.writerow([v.display_name, v.company_name, v.email, v.mobile])

    return response


@login_required
def purchase_order_list(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    min_amount = request.GET.get('min_amount', '').strip()
    max_amount = request.GET.get('max_amount', '').strip()


    orders_list = (
        PurchaseOrder.objects
        .filter(company=company)
        .annotate(
            status_order=Case(
                When(status="DRAFT", then=0),
                When(status="PENDING", then=1),
                When(status="ORDERED", then=2),
                When(status="PARTIAL", then=3),
                When(status="COMPLETED", then=4),
                When(status="RECEIVED", then=5),
                default=6,
                output_field=IntegerField(),
            )
        )
        .order_by("status_order", "-created_at")
    )


    if search:

        if search.isdigit():
            orders_list = orders_list.filter(
                order_number__iregex=rf'^PO-{search}$'
            )

        elif search.upper().startswith("PO-"):
            orders_list = orders_list.filter(
                order_number__iexact=search
            )

        else:
            orders_list = orders_list.filter(
                Q(order_number__icontains=search) |
                Q(vendor__company_name__icontains=search) |
                Q(vendor__display_name__icontains=search)
            )

    if status and status != "ALL":
        orders_list = orders_list.filter(status=status)


    if min_amount:
        try:
            orders_list = orders_list.filter(
                total_amount__gte=Decimal(min_amount)
            )
        except:
            pass

    if max_amount:
        try:
            orders_list = orders_list.filter(
                total_amount__lte=Decimal(max_amount)
            )
        except:
            pass


    paginator = Paginator(orders_list, 10)
    page_number = request.GET.get("page")
    orders = paginator.get_page(page_number)


    in_transit_count = orders_list.filter(
        status__in=['ORDERED', 'PENDING', 'PARTIAL']
    ).count()

    received_count = orders_list.filter(
        status__in=['RECEIVED', 'COMPLETED']
    ).count()

    total_spent = orders_list.filter(
        status__in=['RECEIVED', 'COMPLETED']
    ).aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    return render(
        request,
        "inventory/purchase_order_list.html",
        {
            "orders": orders,
            "company": company,
            "in_transit_count": in_transit_count,
            "received_count": received_count,
            "total_spent": total_spent,
            "search": search,
            "status": status,
            "min_amount": min_amount,
            "max_amount": max_amount,
        }
    )




@login_required
def export_purchase_orders_pdf(request):
    """
    Download Purchase Orders as themed PDF
    """

    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    orders = (
        PurchaseOrder.objects
        .filter(company=company)
        .select_related("vendor")
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_purchase_orders.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )
    
    # ADDED: cell_style for wrapping long text
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        wordWrap="CJK",        # enables wrapping
        splitLongWords=True,   # breaks long words
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Purchase Orders Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    
# 16-4-26
    # UPDATED: header now uses Paragraph (for proper styling consistency)
    data = [
        [
            Paragraph("PO Number", cell_style),
            Paragraph("Vendor", cell_style),
            Paragraph("Status", cell_style),
            Paragraph("Total Amount", cell_style),
            Paragraph("Date", cell_style),
        ]
    ]

    #  UPDATED: wrap ALL cell values using Paragraph
    for order in orders:
        data.append([
            Paragraph(str(order.order_number), cell_style),   # wrap enabled
            Paragraph(
                str(order.vendor.display_name if order.vendor else "-"),
                cell_style
            ),  # wrap long vendor names
            Paragraph(str(order.status), cell_style),
            Paragraph(f"Rs. {order.total_amount}", cell_style),
            Paragraph(order.created_at.strftime("%d-%m-%Y"), cell_style),
        ])
        # 16-4-26

    table = Table(data, colWidths=[100, 150, 90, 100, 80])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9db0db")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response

@login_required
@transaction.atomic
def add_purchase_order(request):
    profile = UserProfile.objects.get(user=request.user)
    vendors = Vendor.objects.filter(company=profile.company)
    products = Product.objects.filter(company=profile.company)
    company = profile.company
    today = date.today()

    if request.method == "POST":
        vendor_id = request.POST.get("vendor")

        try:
            vendor = Vendor.objects.get(
                id=vendor_id,
                company=profile.company
            )
        except Vendor.DoesNotExist:
            messages.error(request, "Selected vendor does not exist.")
            return redirect("add_purchase_order")

        product_ids = request.POST.getlist("product[]")
        quantities = request.POST.getlist("quantity[]")
        cost_prices = request.POST.getlist("cost_price[]")
        batch_numbers = request.POST.getlist("batch_number[]")
        expiry_dates = request.POST.getlist("expiry_date[]")

        if not product_ids:
            messages.error(request, "Please select at least one product.")
            return redirect("add_purchase_order")

        #  Duplicate batch validation
        for i in range(len(product_ids)):
            if not product_ids[i]:
                continue

            product = Product.objects.get(
                id=product_ids[i],
                company=profile.company
            )

            batch_number = batch_numbers[i].strip() if i < len(batch_numbers) else None

            if batch_number:
                exists = PurchaseOrderItem.objects.filter(
                    product=product,
                    batch_number__iexact=batch_number
                ).exists()

                if exists:
                    messages.error(
                        request,
                        f"Batch number '{batch_number}' already exists for product '{product.name}'."
                    )
                    return redirect("add_purchase_order")

        # Wrap the creation process in a try block to catch absolute DB overflows
        try:
            #  Create Purchase Order
            order = PurchaseOrder.objects.create(
                company=profile.company,
                vendor=vendor,
                total_amount=0
            )

            total_amount = Decimal('0.00')

            for index, product_id in enumerate(product_ids):
                if not product_id:
                    continue

                try:
                    product = Product.objects.get(
                        id=product_id,
                        company=profile.company
                    )
                except Product.DoesNotExist:
                    order.delete()
                    messages.error(request, "One of the selected products does not exist.")
                    return redirect("add_purchase_order")

                try:
                    quantity = int(quantities[index])
                    cost_price = Decimal(cost_prices[index]) # Use Decimal instead of float for safety
                except (ValueError, IndexError, InvalidOperation):
                    order.delete()
                    messages.error(request, "Invalid quantity or cost price.")
                    return redirect("add_purchase_order")

                # BOUNDARY VALUE VALIDATIONS (Fixes Bug_019 & Bug_020)
                if quantity <= 0 or quantity > 99999:
                    order.delete()
                    messages.error(request, f"Quantity boundary exceeded for '{product.name}'. Max allowed is 99,999.")
                    return redirect("add_purchase_order")

                if cost_price <= 0 or cost_price >= Decimal('100000000.00'):
                    order.delete()
                    messages.error(request, f"Cost price boundary exceeded for '{product.name}'. Max allowed is ₹99,999,999.99.")
                    return redirect("add_purchase_order")

                item_total = quantity * cost_price
                if item_total >= Decimal('100000000.00'):
                    order.delete()
                    messages.error(request, f"Total value of '{product.name}' (Qty × Price) exceeds maximum limit of ₹99,999,999.99.")
                    return redirect("add_purchase_order")
                
                if total_amount + item_total >= Decimal('100000000.00'):
                    order.delete()
                    messages.error(request, "Overall order total exceeds maximum database limit of ₹99,999,999.99.")
                    return redirect("add_purchase_order")
                
                expiry_date = (
                    expiry_dates[index].strip()
                    if index < len(expiry_dates) and expiry_dates[index].strip()
                    else None
                )

            
                if expiry_date:
                    try:
                        expiry_date_obj = datetime.strptime(expiry_date, "%Y-%m-%d").date()
                    except ValueError:
                        order.delete()
                        messages.error(request, f"Invalid expiry date format for '{product.name}'.")
                        return redirect("add_purchase_order")

                    if expiry_date_obj < date.today():
                        order.delete()
                        messages.error(
                            request,
                            f"Expiry date cannot be in the past for '{product.name}'."
                        )

                        return redirect("add_purchase_order")



                batch_number = (
                    batch_numbers[index].strip()
                    if index < len(batch_numbers) and batch_numbers[index].strip()
                    else None
                )

                expiry_date = (
                    expiry_dates[index].strip()
                    if index < len(expiry_dates) and expiry_dates[index].strip()
                    else None
                )

                #  Mandatory validation for expiry tracked products
                if product.is_expiry_tracked and (not batch_number or not expiry_date):
                    order.delete()
                    messages.error(
                        request,
                        f"Batch number and expiry date are required for {product.name}."
                    )
                    return redirect("add_purchase_order")

                PurchaseOrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=quantity,
                    cost_price=cost_price,
                    batch_number=batch_number,
                    expiry_date=expiry_date
                )

                total_amount += item_total

            order.total_amount = total_amount
            order.order_number = f"PO-{order.id}"
            order.save(update_fields=["total_amount", "order_number"])

            messages.success(request, "Purchase order created successfully.")

            return render(
                request,
                "inventory/add_purchase_order.html",
                {
                    "vendors": vendors,
                    "products": products,
                    "min_expiry_date": today,
                    "company": company,
                }
            )
            
        except DataError:
            # Fallback: Catch any extreme numeric overflow hitting Postgres/MySQL 
            messages.error(request, "Numeric bounds exceeded on database column saving.")
            return redirect("add_purchase_order")

    return render(
        request,
        "inventory/add_purchase_order.html",
        {
            "vendors": vendors,
            "products": products,
            "min_expiry_date": today,
            "company": company,
        }
    )






@login_required
def batch_stock_list(request):

    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return redirect("company_login")

    company = profile.company

    status = request.GET.get("status")
    today = date.today()
    near_limit = today + timedelta(days=30)

    # BASE QUERY
    batches = ProductBatch.objects.filter(
        company=company,
        quantity__gt=0
    ).select_related("product")

    all_batches = batches

    total_batches = all_batches.count()

    expired_count = all_batches.filter(
        expiry_date__lt=today,
        is_active=True
    ).count()

    near_expiry_count = all_batches.filter(
        expiry_date__gte=today,
        expiry_date__lte=near_limit
    ).count()

    active_count = all_batches.filter(
        expiry_date__gt=near_limit
    ).count()

    good_condition_percent = (
        round((active_count / total_batches) * 100)
        if total_batches > 0 else 0
    )

    # STATUS FILTER
    if status == "expired":
        batches = batches.filter(expiry_date__lt=today)

    elif status == "near_expiry":
        batches = batches.filter(
            expiry_date__gte=today,
            expiry_date__lte=near_limit
        )

    else:
        batches = batches.filter(expiry_date__gte=today)

    # SEARCH
    query = request.GET.get("q", "").strip()

    if query:
        batches = batches.filter(
            Q(batch_number__icontains=query) |
            Q(product__name__icontains=query)
        )

    batches = batches.order_by("expiry_date")

    #  PAGINATION ADD
    paginator = Paginator(batches, 10)   # 10 records per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/batch_stock_list.html",
        {
            "batches": page_obj,    
            "page_obj": page_obj,   
            "expired_count": expired_count,
            "near_expiry_count": near_expiry_count,
            "active_count": active_count,
            "good_condition_percent": good_condition_percent,
            "active_filter": status,
            "search_query": query,
            "company": company,
        }
    )



@login_required
def stock_aging_report(request):
    profile = UserProfile.objects.get(user=request.user)
    today = date.today()

    batches = ProductBatch.objects.filter(
        company=profile.company,
        quantity__gt=0
    )

    aging_data = {
        "0_30": [],
        "31_60": [],
        "60_plus": []
    }

    for b in batches:
        age_days = (today - b.created_at.date()).days

        if age_days <= 30:
            aging_data["0_30"].append(b)
        elif age_days <= 60:
            aging_data["31_60"].append(b)
        else:
            aging_data["60_plus"].append(b)

    return render(
        request,
        "inventory/stock_aging_report.html",
        {"aging_data": aging_data}
    )


@login_required
def product_stock_breakdown(request, pk):

    # Get logged in user's company
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    # Company-wise product protection (important)
    product = get_object_or_404(
        Product,
        id=pk,
        company=company
    )

    batches = ProductBatch.objects.filter(
        product=product,
        company=company
    )

    total_stock = batches.aggregate(
        total=Sum("quantity")
    )["total"] or 0

    today = date.today()
    near_limit = today + timedelta(days=30)

    expiring_soon_count = ProductBatch.objects.filter(
        product=product,
        company=company,
        expiry_date__gte=today,
        expiry_date__lte=near_limit,
        quantity__gt=0,
        is_active=True
    ).count()

    context = {
        "product": product,
        "batches": batches,
        "total_stock": total_stock,
        "expiring_soon_count": expiring_soon_count,
        "today": today,
        "company": company,   
    }

    return render(
        request,
        "inventory/product_stock_breakdown.html",
        context
    )




@login_required
def adjust_batch_stock(request):
    #  Get user profile & company
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return redirect("company_login")

    company = profile.company

    #  IMPORTANT: company-wise products
    products = Product.objects.filter(company=company)

    if request.method == "POST":
        product_id = request.POST.get("product")
        batch_number = request.POST.get("batch_number")
        adjustment_type = request.POST.get("adjustment_type")
        quantity_raw = request.POST.get("quantity")
        reason = request.POST.get("reason", "").strip()

        #  Validate product
        if not product_id:
            messages.error(request, "Please select a product.")
            return redirect("adjust_batch_stock")

        try:
            product = Product.objects.get(id=product_id, company=company)
        except Product.DoesNotExist:
            messages.error(request, "Selected product does not exist.")
            return redirect("adjust_batch_stock")

        #  Validate quantity strictly to prevent Overflow errors
        if not quantity_raw:
            messages.error(request, "Quantity cannot be empty.")
            return redirect("adjust_batch_stock")
            
        try:
            quantity = int(quantity_raw)
        except ValueError:
            messages.error(request, "Quantity must be a valid whole number.")
            return redirect("adjust_batch_stock")

        if quantity <= 0:
            messages.error(request, "Quantity must be greater than 0.")
            return redirect("adjust_batch_stock")
            
        #  Prevent DB Overflow Error (Postgres IntegerField max is 2,147,483,647)
        if quantity > 100000000:
            messages.error(request, "Quantity is too large. Maximum allowed adjustment is 100,000,000.")
            return redirect("adjust_batch_stock")

        #  Mandatory reason
        if not reason:
            messages.error(request, "Adjustment reason is mandatory.")
            return redirect("adjust_batch_stock")

        #  Get or create batch
        batch, _ = ProductBatch.objects.get_or_create(
            company=company,
            product=product,
            batch_number=batch_number,
            defaults={
                "expiry_date": date.today(),
                "quantity": 0
            }
        )

        old_qty = batch.quantity

        today = timezone.now().date()

        if batch.expiry_date and batch.expiry_date < today:
            messages.error(
                request,
                "Stock adjustment is blocked. This batch is expired."
            )
            return redirect("adjust_batch_stock")

        #  Restrict invalid removal
        if adjustment_type == "remove" and quantity > batch.quantity:
            messages.error(
                request,
                f"Cannot remove {quantity}. Available stock is {batch.quantity}."
            )
            return redirect("adjust_batch_stock")

        #  Block inactive batch
        if hasattr(batch, "is_active") and not batch.is_active:
            messages.error(request, "Cannot adjust an inactive batch.")
            return redirect("adjust_batch_stock")

        #  Apply adjustment
        if adjustment_type == "add":
            # Safety check against DB overflow after addition
            if batch.quantity + quantity > 2000000000:
                 messages.error(request, "Total stock exceeds database limits.")
                 return redirect("adjust_batch_stock")
            batch.quantity += quantity
        elif adjustment_type == "remove":
            batch.quantity -= quantity
        else:
            messages.error(request, "Invalid adjustment type.")
            return redirect("adjust_batch_stock")

        batch.save(update_fields=["quantity"])
        new_qty = batch.quantity

        #  Audit log
        transaction_type = "IN" if adjustment_type == "add" else "OUT"

        StockTransaction.objects.create(
            company=company,
            product=product,
            batch=batch,
            transaction_type=transaction_type,   
            source="MANUAL",
            quantity=abs(new_qty - old_qty),
            reference_number=f"ADJUST-{batch.id}",
            created_by=request.user,
            note=f"{reason} | Old: {old_qty}, New: {new_qty}"
        )

        reconcile_product_stock(company)

        messages.success(
            request,
            f"Stock for batch '{batch.batch_number}' adjusted successfully."
        )
        
        return redirect("adjust_batch_stock")


    return render(
        request,
        "inventory/adjust_batch_stock.html",
        {
            "products": products,
            "company": company,  #  THIS enables {{ company.name }} in header
        }
    )


def safe_deduct_batch(batch, qty):
    if batch.quantity < qty:
        raise ValidationError(
            f"Insufficient stock in batch {batch.batch_number}"
        )
    batch.quantity -= qty
    batch.save(update_fields=["quantity"])

from django.db.models.functions import Lower, Trim
import re

@login_required
def add_vendor(request):
    company = owner_required(request)
    errors = {}

    if request.method == "POST":

        salutation = request.POST.get("salutation")

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")

        #  normalize company name (fix duplicate issue)
        company_name = re.sub(r'\s+', ' ', request.POST.get("company_name", "")).strip()
        gst_number = request.POST.get("gst_number", "").upper()

        display_name = request.POST.get("display_name")

        email = request.POST.get("email")
        mobile = request.POST.get("mobile")

        language = request.POST.get("language")
        address = request.POST.get("address")

        # ---------- GST VALIDATION ----------
        gst_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'

        if not gst_number:
            errors["gst_number"] = "GST number is required."

        elif not re.match(gst_regex, gst_number):
            errors["gst_number"] = "Invalid GST format (e.g. 22AAAAA0000A1Z5)."

        elif Vendor.objects.filter(company=company, gst_number=gst_number).exists():
            errors["gst_number"] = "Vendor with this GST already exists."

        # ---------- BASIC VALIDATIONS ----------
        if not first_name:
            errors["first_name"] = "First name required."

        if not last_name:
            errors["last_name"] = "Last name required."

        if not company_name:
            errors["company_name"] = "Company name required."

        elif len(company_name) > 50:
            errors["company_name"] = "Maximum 50 characters allowed."

        # ---------- DUPLICATE CHECKS (FIXED) ----------
        elif Vendor.objects.annotate(
            clean_name=Lower(Trim('company_name'))
        ).filter(
            company=company,
            clean_name=company_name.lower()
        ).exists():
            errors["company_name"] = "Vendor with this company name already exists."

        if mobile and Vendor.objects.filter(company=company, mobile=mobile).exists():
            errors["mobile"] = "Vendor with this mobile number already exists."

        if email and Vendor.objects.filter(company=company, email__iexact=email).exists():
            errors["email"] = "Vendor with this email already exists."

        # ---------- MOBILE VALIDATION ----------
        if not mobile or not mobile.isdigit() or len(mobile) != 10:
            errors["mobile"] = "Valid 10-digit mobile required."

        # ---------- EMAIL VALIDATION ----------
        if email:
            try:
                validate_email(email)
            except:
                errors["email"] = "Invalid email format."

        # ---------- RETURN ERRORS ----------
        if errors:
            return render(request, "inventory/add_vendor.html", {
                "company": company,
                "errors": errors,
                "post_data": request.POST
            })

        # ---------- CREATE VENDOR ----------
        Vendor.objects.create(
            company=company,
            salutation=salutation,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            gst_number=gst_number,
            display_name=display_name,
            email=email,
            mobile=mobile,
            language=language,
            address=address,
        )

        messages.success(request, "Vendor added successfully")
        return redirect("vendor_list")

    return render(request, "inventory/add_vendor.html", {
        "company": company
    })





@login_required
@transaction.atomic
def purchase_order_detail(request, pk):
    # Assuming UserProfile is correctly imported
    profile = request.user.userprofile 
    company = profile.company

    order = get_object_or_404(
        PurchaseOrder,
        id=pk,
        company=company
    )

    items = order.items.select_related("product")

    
    #  BLOCK INVALID STATES
    
    if request.method == "POST" and order.status == "DRAFT":
        messages.error(request, "Submit Purchase Order before receiving stock.")
        return redirect("purchase_orders")

    if order.status == "RECEIVED":
        return render(
            request,
            "inventory/purchase_order_detail.html",
            {
                "order": order,
                "items": items,
                "company": company,
            }
        )

    
    #  RECEIVE LOGIC (PARTIAL)
    
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        received_qty = request.POST.get("received_qty")

        if not item_id or not received_qty:
            messages.error(request, "Invalid request")
            return redirect("purchase_order_detail", pk=pk)

        item = get_object_or_404(
            PurchaseOrderItem,
            id=item_id,
            order=order
        )

        try:
            received_qty = int(received_qty)
        except ValueError:
            messages.error(request, "Invalid quantity")
            return redirect("purchase_order_detail", pk=pk)

        remaining = item.quantity - item.received_quantity

        
        #  VALIDATIONS
        
        if received_qty < 0:
            messages.error(request, "Quantity cannot be negative")
            return redirect("purchase_order_detail", pk=pk)

        #  HANDLE ZERO (NO STOCK RECEIVED)
        if received_qty == 0:
            messages.warning(request, "No stock received for this item")
            return redirect("purchase_order_detail", pk=pk)

        if received_qty > remaining:
            messages.error(request, "Cannot receive more than remaining quantity")
            return redirect("purchase_order_detail", pk=pk)

        product = item.product

        
        #  BATCH LOGIC
        
        if product.is_expiry_tracked:
            batch_number = item.batch_number
            expiry_date = item.expiry_date
        else:
            batch_number = item.batch_number if item.batch_number else "NO-BATCH"
            expiry_date = None # <-- FIX: Changed from date(2099, 12, 31) to None

        batch, created = ProductBatch.objects.get_or_create(
            company=company,
            product=product,
            batch_number=batch_number,
            defaults={
                "expiry_date": expiry_date,
                "quantity": 0
            }
        )

        #  UPDATE BATCH STOCK (ONLY RECEIVED)
        batch.quantity += received_qty
        batch.save(update_fields=["quantity"])

        
        #  UPDATE ITEM RECEIVED
        
        item.received_quantity += received_qty
        item.save(update_fields=["received_quantity"])

        
        #  UPDATE PRODUCT STOCK
        
        product.purchase_price = item.cost_price

        product.stock_quantity = ProductBatch.objects.filter(
            company=company,
            product=product
        ).aggregate(total=Sum("quantity"))["total"] or 0

        product.save(update_fields=["purchase_price", "stock_quantity"])

        
        #  STOCK TRANSACTION LOG
        
        StockTransaction.objects.create(
            company=company,
            product=product,
            transaction_type="IN",
            source="PURCHASE",
            quantity=received_qty,
            reference_number=order.order_number,
            created_by=request.user
        )

        
        #  UPDATE ORDER STATUS
        
        all_received = all(
            i.received_quantity == i.quantity for i in order.items.all()
        )

        any_received = any(
            i.received_quantity > 0 for i in order.items.all()
        )

        if all_received:
            order.status = "RECEIVED"
        elif any_received:
            order.status = "PARTIAL"
        else:
            order.status = "ORDERED"

        order.save(update_fields=["status"])

        messages.success(request, "Stock received successfully")
        return redirect("purchase_order_detail", pk=pk)

    
    # GET REQUEST
@transaction.atomic
def purchase_order_detail(request, pk):
    profile = request.user.userprofile 
    company = profile.company

    order = get_object_or_404(
        PurchaseOrder,
        id=pk,
        company=company
    )

    items = order.items.select_related("product")

    if request.method == "POST" and order.status == "DRAFT":
        messages.error(request, "Submit Purchase Order before receiving stock.")
        return redirect("purchase_orders")

    if order.status == "RECEIVED":
        return render(
            request,
            "inventory/purchase_order_detail.html",
            {
                "order": order,
                "items": items,
                "company": company,
            }
        )

    if request.method == "POST":
        item_id = request.POST.get("item_id")
        received_qty = request.POST.get("received_qty")

        if not item_id or not received_qty:
            messages.error(request, "Invalid request")
            return redirect("purchase_order_detail", pk=pk)

        item = get_object_or_404(
            PurchaseOrderItem,
            id=item_id,
            order=order
        )

        try:
            received_qty = int(received_qty)
        except ValueError:
            messages.error(request, "Invalid quantity")
            return redirect("purchase_order_detail", pk=pk)

        remaining = item.quantity - item.received_quantity

        if received_qty < 0:
            messages.error(request, "Quantity cannot be negative")
            return redirect("purchase_order_detail", pk=pk)

        if received_qty == 0:
            messages.warning(request, "No stock received for this item")
            return redirect("purchase_order_detail", pk=pk)

        if received_qty > remaining:
            messages.error(request, "Cannot receive more than remaining quantity")
            return redirect("purchase_order_detail", pk=pk)

        product = item.product

        if product.is_expiry_tracked:
            batch_number = item.batch_number
            expiry_date = item.expiry_date
        else:
            batch_number = item.batch_number if item.batch_number else "NO-BATCH"
            expiry_date = None

        batch, created = ProductBatch.objects.get_or_create(
            company=company,
            product=product,
            batch_number=batch_number,
            defaults={
                "expiry_date": expiry_date,
                "quantity": 0
            }
        )

        batch.quantity += received_qty
        batch.save(update_fields=["quantity"])

        item.received_quantity += received_qty
        item.save(update_fields=["received_quantity"])

        product.purchase_price = item.cost_price

        product.stock_quantity = ProductBatch.objects.filter(
            company=company,
            product=product
        ).aggregate(total=Sum("quantity"))["total"] or 0

        product.save(update_fields=["purchase_price", "stock_quantity"])

        StockTransaction.objects.create(
            company=company,
            product=product,
            transaction_type="IN",
            source="PURCHASE",
            quantity=received_qty,
            reference_number=order.order_number,
            created_by=request.user
        )

        all_received = all(
            i.received_quantity == i.quantity for i in order.items.all()
        )

        any_received = any(
            i.received_quantity > 0 for i in order.items.all()
        )

        if all_received:
            order.status = "RECEIVED"
        elif any_received:
            order.status = "PARTIAL"
        else:
            order.status = "ORDERED"

        order.save(update_fields=["status"])

        messages.success(request, "Stock received successfully")
        return redirect("purchase_order_detail", pk=pk)

    return render(
        request,
        "inventory/purchase_order_detail.html",
        {
            "order": order,
            "items": items,
            "company": company,
        }
    )




def export_sales_excel(request):
    company = request.user.userprofile.company

    #  GET DATA
    purchases = PurchaseOrderItem.objects.filter(
        order__company=company
    ).select_related('product', 'order')

    #  CREATE WORKBOOK
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sales Report"

    #  HEADERS
    headers = ["Date", "Product", "Quantity", "Cost Price", "Amount"]
    ws.append(headers)

    # Bold header
    for col in ws[1]:
        col.font = Font(bold=True)

    #  ADD DATA
    for item in purchases:
        amount = item.quantity * item.cost_price

        ws.append([
            item.order.created_at.strftime("%Y-%m-%d"),
            item.product.name,
            item.quantity,
            float(item.cost_price),
            float(amount)
        ])

    #  APPLY ₹ FORMAT
    for row in ws.iter_rows(min_row=2, min_col=4, max_col=5):
        for cell in row:
            cell.number_format = '₹#,##0.00'

    #  AUTO WIDTH
    for col in ws.columns:
        max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_length + 2

    #  RESPONSE
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response['Content-Disposition'] = 'attachment; filename=Sales_Report.xlsx'

    wb.save(response)
    return response



@login_required
def export_sales_pdf(request):

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="sales_report.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # HEADER
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1
    )

    header_table = Table(
        [[Paragraph("Purchase Stock Report", header_style)]],
        colWidths=[520]
    )

    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#16a34a")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(header_table)

    # DATE
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    
    # FETCH DATA
    
    company = request.user.userprofile.company

    purchases = PurchaseOrderItem.objects.filter(
        order__company=company
    ).select_related("product", "order")

    
    # TABLE DATA
    
    data = [["Date", "Product", "Qty", "Cost Price", "Amount (Rs.)"]]

    total_amount = 0

    for item in purchases:
        quantity = item.quantity or 0
        cost_price = float(item.cost_price or 0)
        amount = quantity * cost_price

        total_amount += amount

        data.append([
            item.order.created_at.strftime("%d-%m-%Y"),
            item.product.name,
            quantity,
            f"Rs. {cost_price:,.2f}",
            f"Rs. {amount:,.2f}"
        ])

    
    # TOTAL ROW
    
    data.append([
        "", "", "", "Total",
        f"₹ {total_amount:,.2f}"
    ])

    
    # TABLE DESIGN
    
    table = Table(data, colWidths=[90, 160, 60, 100, 110])

    table.setStyle(TableStyle([

        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 9),

        # Align amount right
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"),

        # Alternate rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -2),
         [colors.HexColor("#f1f5f9"), colors.white]),

        # Total row
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),

        # Borders
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),

        # Padding
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    
    # BUILD PDF
    
    doc.build(elements)

    return response



@login_required
def all_transactions(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    qs = SalesOrder.objects.filter(company=company).order_by("-created_at")
    
    paginator = Paginator(qs, 10)  # 10 items per page
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    return render(request, "inventory/all_transactions.html", {
        "company": company,
        "orders": page_obj.object_list,
        "page_obj": page_obj,
    })





@login_required
def add_stock(request):
    #  get company correctly
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    products = Product.objects.filter(company=company)

    if request.method == "POST":
        product_id = request.POST.get("product")
        quantity = int(request.POST.get("quantity"))
        purchase_price = request.POST.get("purchase_price")

        product = get_object_or_404(
            Product,
            id=product_id,
            company=company
        )

        #  update stock
        product.stock_quantity += quantity
        product.purchase_price = purchase_price
        product.save()

        messages.success(request, "Stock added successfully")
        return redirect("product_list")

    return render(request, "inventory/add_stock.html", {
        "products": products
    })






@login_required
def customer_export_excel(request):
    wb = Workbook()

    ws = wb.active
    ws.title = "Customers"

    headers = [
        "ID", "Contact Name", "Company Name", "Customer Type",
        "Email", "Phone", "Website", "Currency",
        "Payment Terms", "Credit Limit", "GST Number",
        "Place of Supply", "Notes"
    ]
    ws.append(headers)

    for c in Customer.objects.all():
        ws.append([
            c.id,
            c.contact_name or "",
            c.company_name or "",
            c.customer_type or "",
            c.email or "",
            c.phone or "",
            c.website or "",
            c.currency or "",
            c.payment_terms or "",
            c.credit_limit or "",
            c.gst_number or "",
            c.place_of_supply or "",
            c.notes or "",
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=customers.xlsx"

    wb.save(response)
    return response





def quote_create(request):
    if request.method == "POST":
        form = QuoteForm(request.POST)
        formset = QuoteItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            quote = form.save(commit=False)
            quote.quote_number = f"QT-{uuid.uuid4().hex[:6].upper()}"

            subtotal = Decimal("0")

            quote.save()
            formset.instance = quote

            items = formset.save(commit=False)
            for item in items:
                item.amount = item.quantity * item.rate
                subtotal += item.amount
                item.save()

            quote.subtotal = subtotal
            quote.total = subtotal
            quote.save()

            return redirect('inventory:quote_list')

    else:
        form = QuoteForm()
        formset = QuoteItemFormSet()

    return render(
        request,
        'inventory/Quote_form.html',
        {
            'form': form,
            'formset': formset
        }
    )


def quote_list(request):
    quotes = Quote.objects.all().order_by('-created_at')
    return render(request, 'inventory/quote_list.html', {'quotes': quotes})

def quote_create(request):
    customers = Customer.objects.all()
    products = Product.objects.all()

    if request.method == "POST":
        # your existing save logic
        pass

    return render(request, "inventory/quotes_create.html", {
        "customers": customers,
        "products": products
    })



def purchase_order_print(request, pk):
    order = get_object_or_404(PurchaseOrder, pk=pk)

    #  CORRECT URL (NO DUPLICATE inventory)
    print_url = request.build_absolute_uri(
        f"/inventory/purchase-orders/{order.pk}/print/"
    )

    # Generate QR
    qr = qrcode.make(print_url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(
        request,
        "inventory/purchase_order_print.html",
        {
            "order": order,
            "qr_code": qr_base64,
            "print_url": print_url,
        }
    )


@login_required
def export_vendors_pdf(request):
    """
    Download Vendors list as themed PDF
    """

    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    vendors = Vendor.objects.filter(company=company).order_by("display_name")

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_vendors.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.white,
        alignment=1,
        spaceAfter=10
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Vendor List", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Cell styles
    cell_style = ParagraphStyle(
        'cell', fontSize=9, leading=12, wordWrap='LTR'
    )
    header_cell_style = ParagraphStyle(
        'header_cell', fontSize=10, leading=12,
        textColor=colors.white, fontName='Helvetica-Bold'
    )

    # Table data
    data = [
        [
            Paragraph("Vendor Name", header_cell_style),
            Paragraph("Company", header_cell_style),
            Paragraph("Email", header_cell_style),
            Paragraph("Phone", header_cell_style),
        ]
    ]

    for v in vendors:
        data.append([
            Paragraph(v.display_name or "-", cell_style),
            Paragraph(v.company_name or "-", cell_style),
            Paragraph(v.email or "-", cell_style),
            Paragraph(v.mobile or "-", cell_style),
        ])

    table = Table(data, colWidths=[130, 120, 160, 80], repeatRows=1)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    elements.append(table)

    doc.build(elements)
    return response



@login_required
def export_sales_orders_pdf(request):
    """
    Download Sales Orders as themed PDF
    """

    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    sales_orders = (
        SalesOrder.objects
        .filter(company=company)
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_sales_orders.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Sales Orders Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Table data
    data = [
        ["Order No", "Customer", "Status", "Total Amount", "Date"]
    ]

    for order in sales_orders:
        data.append([
            order.order_number,
            order.customer_name or "-",
            order.status,
            f"Rs. {order.total_amount}",
            order.created_at.strftime("%d-%m-%Y"),
        ])

    table = Table(data, colWidths=[100, 150, 90, 100, 80])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response



@login_required
def export_sales_orders_pdf(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    sales_orders = (
        SalesOrder.objects
        .filter(company=company)
        .order_by("-created_at")
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_sales_orders.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    #  NEW: Customer text wrap style
    wrap_style = ParagraphStyle(
        name="WrapStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        wordWrap='CJK',   # helps break long words
        alignment=TA_LEFT
    )

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Sales Orders Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Table data
    data = [
        ["Order No", "Customer", "Status", "Total Amount", "Date"]
    ]

    for order in sales_orders:
        customer_name = order.customer_name or "-"

        #  FIX: Wrap customer name using Paragraph
        customer_para = Paragraph(customer_name, wrap_style)

        data.append([
            order.order_number,
            customer_para,   # 👈 FIX APPLIED HERE
            order.status,
            f"Rs. {order.total_amount}",
            order.created_at.strftime("%d-%m-%Y"),
        ])

    #  OPTIONAL: Slightly increase customer column width
    table = Table(data, colWidths=[90, 180, 80, 90, 80])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),

        #  IMPORTANT: vertical alignment for wrapped text
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response




@login_required
def export_inventory_pdf(request):
    """
    Download Inventory (Products) as Colorful PDF
    """

    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    products = (
        Product.objects
        .filter(company=company)
        .only("name", "sku", "stock_quantity", "selling_price")
        .order_by("-id")
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_inventory.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.white,
        alignment=1,
        spaceAfter=10
    )

    # Header table
    header_data = [[
        Paragraph(f"{company.name} - Inventory Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Cell styles for word wrap
    cell_style = ParagraphStyle(
        'cell', fontSize=9, leading=12, wordWrap='LTR'
    )
    header_cell_style = ParagraphStyle(
        'header_cell', fontSize=10, leading=12,
        textColor=colors.white, fontName='Helvetica-Bold'
    )

    # Table data
    data = [
        [
            Paragraph("Product Detail", header_cell_style),
            Paragraph("SKU Code", header_cell_style),
            Paragraph("Current Stock", header_cell_style),
            Paragraph("Unit Price", header_cell_style),
        ]
    ]

    for p in products:
        data.append([
            Paragraph(p.name or "-", cell_style),
            Paragraph(p.sku or "-", cell_style),
            Paragraph(str(p.stock_quantity), cell_style),
            Paragraph(f"Rs. {intcomma(int(p.selling_price))}", cell_style),
        ])

    # Main table
    table = Table(data, colWidths=[200, 110, 80, 100], repeatRows=1)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    elements.append(table)

    doc.build(elements)
    return response



@login_required
def export_batch_stock_pdf(request):
    """
    Export Batch-wise Stock as themed PDF
    """

    # Get logged-in company
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    # Fetch batch stock
    batches = get_batch_stock_queryset(request, company)

    # Prepare PDF response
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="{company.name}_batch_stock.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=40,
        bottomMargin=20
    )

    elements = []
    styles = getSampleStyleSheet()

    # Header style
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    #  FIX: Cell wrap style for long text
    cell_style = ParagraphStyle(
        "CellWrap",
        parent=styles["Normal"],
        fontSize=9,
        wordWrap="CJK",
        leading=12,
    )

    # Header bar
    header_data = [[
        Paragraph(f"{company.name} - Batch Stock Report", header_style)
    ]]

    header_table = Table(header_data, colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)

    # Date
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Table data
    data = [
        ["Product", "Batch No", "Expiry Date", "Quantity", "Status"]
    ]

    #  FIX: Wrap product name and batch number in Paragraph to enable word wrap
    for b in batches:
        data.append([
            Paragraph(b.product.name if b.product else "-", cell_style),
            Paragraph(b.batch_number if b.batch_number else "-", cell_style),
            b.expiry_date.strftime("%d-%m-%Y") if b.expiry_date else "-",
            str(b.quantity),
            b.expiry_status,
        ])

    #  FIX: Adjusted colWidths so total = 520, Product column has enough room
    table = Table(data, colWidths=[150, 100, 95, 70, 85])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),

        #  FIX: Allow rows to grow in height for wrapped text
        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))

    elements.append(table)

    doc.build(elements)
    return response

from datetime import date, timedelta
from django.db.models import Sum
from inventory.models import Product, ProductBatch, InventoryAlert


def reconcile_product_stock(company):
    today = date.today()

    products = Product.objects.filter(company=company)

    for product in products:
        #  Calculate correct stock from valid batches
        correct_stock = (
            ProductBatch.objects.filter(
                company=company,
                product=product,
                expiry_date__gte=today,
                quantity__gt=0,
                is_active=True
            )
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        #  Reconcile mismatch
        if product.stock_quantity != correct_stock:
            product.stock_quantity = correct_stock
            product.save(update_fields=["stock_quantity"])

        #  INVENTORY ALERTS (AUTO-GENERATED)

        #  OUT OF STOCK
        if correct_stock == 0:
            InventoryAlert.objects.get_or_create(
                company=company,
                product=product,
                alert_type="OUT_OF_STOCK",
                defaults={
                    "severity": "HIGH",
                    "message": f"{product.name} is out of stock."
                }
            )

        #  LOW STOCK
        elif correct_stock <= product.low_stock_limit:
            InventoryAlert.objects.get_or_create(
                company=company,
                product=product,
                alert_type="LOW_STOCK",
                defaults={
                    "severity": "MEDIUM",
                    "message": f"{product.name} is low on stock ({correct_stock} units left)."
                }
            )

        #  CLEAN UP RESOLVED ALERTS (OPTIONAL BUT RECOMMENDED)
        else:
            InventoryAlert.objects.filter(
                company=company,
                product=product,
                alert_type__in=["LOW_STOCK", "OUT_OF_STOCK"],
                is_read=False
            ).update(is_read=True)

    #  NEAR-EXPIRY ALERTS (BATCH LEVEL)
    near_expiry_limit = today + timedelta(days=30)

    near_expiry_batches = ProductBatch.objects.filter(
        company=company,
        expiry_date__range=[today, near_expiry_limit],
        quantity__gt=0,
        is_active=True
    )

    for batch in near_expiry_batches:
        InventoryAlert.objects.get_or_create(
            company=company,
            batch=batch,
            alert_type="NEAR_EXPIRY",
            defaults={
                "severity": "MEDIUM",
                "message": (
                    f"Batch {batch.batch_number} of "
                    f"{batch.product.name} is near expiry "
                    f"(Exp: {batch.expiry_date})."
                )
            }
        )



@login_required
def get_batch_stock(request):
    profile = UserProfile.objects.get(user=request.user)

    product_id = request.GET.get("product")
    batch_number = request.GET.get("batch")

    quantity = 0

    if product_id and batch_number:
        batch = ProductBatch.objects.filter(
            company=profile.company,
            product_id=product_id,
            batch_number=batch_number,
            is_active=True
        ).first()

        if batch:
            quantity = batch.quantity

    return JsonResponse({"quantity": quantity})
    




def customer_list(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    customers_qs = Customer.objects.filter(company=company)

    #  FILTERS (if any)
    name = request.GET.get("name")
    email = request.GET.get("email")

    if name:
        customers_qs = customers_qs.filter(contact_name__icontains=name)

    if email:
        customers_qs = customers_qs.filter(email__icontains=email)

    
    paginator = Paginator(customers_qs.order_by("-id"), 10)  # 10 per page
    page_number = request.GET.get("page")
    customers = paginator.get_page(page_number)

    return render(request, "inventory/customer_list.html", {
        "customers": customers
    })



@login_required
def customer_create(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    AddressFormSet = inlineformset_factory(
        Customer, Address, form=AddressForm, extra=1, can_delete=True
    )

    ContactFormSet = inlineformset_factory(
        Customer, ContactPerson, form=ContactPersonForm, extra=1, can_delete=True
    )

    if request.method == "POST":

        form = CustomerForm(request.POST)

        address_formset = AddressFormSet(
            request.POST,
            prefix="addresses"
        )

        contact_formset = ContactFormSet(
            request.POST,
            prefix="contacts"
        )

        if form.is_valid() and address_formset.is_valid() and contact_formset.is_valid():
            custom_has_error = False
            
            # --- 1. MAIN CUSTOMER VALIDATION ---
            email = form.cleaned_data.get('email')
            mobile = form.cleaned_data.get('mobile')
            gst_number = form.cleaned_data.get('gst_number')

            if email and Customer.objects.filter(company=company, email=email).exists():
                form.add_error('email', 'A customer with this email already exists.')
                custom_has_error = True

            if mobile and Customer.objects.filter(company=company, mobile=mobile).exists():
                form.add_error('mobile', 'A customer with this mobile number already exists.')
                custom_has_error = True

            if gst_number and Customer.objects.filter(company=company, gst_number=gst_number).exists():
                form.add_error('gst_number', 'A customer with this GST number already exists.')
                custom_has_error = True

            # --- 2. CONTACT PERSON VALIDATION ---
            for c_form in contact_formset:
                if c_form.cleaned_data and not c_form.cleaned_data.get('DELETE', False):
                    c_email = c_form.cleaned_data.get('email')
                    c_phone = c_form.cleaned_data.get('phone') or c_form.cleaned_data.get('mobile')

                    if c_email and ContactPerson.objects.filter(customer__company=company, email=c_email).exists():
                        c_form.add_error('email', 'A contact with this email already exists.')
                        custom_has_error = True
                    
                    if c_phone:
                        # Safely check phone/mobile depending on what your model uses
                        try:
                            if ContactPerson.objects.filter(customer__company=company, phone=c_phone).exists():
                                field_name = 'phone' if 'phone' in c_form.fields else 'mobile'
                                c_form.add_error(field_name, 'A contact with this phone already exists.')
                                custom_has_error = True
                        except: pass
                        
                        try:
                            if ContactPerson.objects.filter(customer__company=company, mobile=c_phone).exists():
                                field_name = 'mobile' if 'mobile' in c_form.fields else 'phone'
                                c_form.add_error(field_name, 'A contact with this mobile already exists.')
                                custom_has_error = True
                        except: pass

            # --- 3. ADDRESS VALIDATION ---
            for a_form in address_formset:
                if a_form.cleaned_data and not a_form.cleaned_data.get('DELETE', False):
                    a_email = a_form.cleaned_data.get('email')
                    a_phone = a_form.cleaned_data.get('phone') or a_form.cleaned_data.get('mobile')

                    if a_email and Address.objects.filter(customer__company=company, email=a_email).exists():
                        a_form.add_error('email', 'An address with this email already exists.')
                        custom_has_error = True

                    if a_phone:
                        try:
                            if Address.objects.filter(customer__company=company, phone=a_phone).exists():
                                field_name = 'phone' if 'phone' in a_form.fields else 'mobile'
                                a_form.add_error(field_name, 'An address with this phone already exists.')
                                custom_has_error = True
                        except: pass
                        
                        try:
                            if Address.objects.filter(customer__company=company, mobile=a_phone).exists():
                                field_name = 'mobile' if 'mobile' in a_form.fields else 'phone'
                                a_form.add_error(field_name, 'An address with this mobile already exists.')
                                custom_has_error = True
                        except: pass

            # --- SAVE IF NO CUSTOM ERRORS ---
            if not custom_has_error:
                with transaction.atomic():
                    customer = form.save(commit=False)
                    customer.company = company   #  IMPORTANT
                    customer.save()

                    address_formset.instance = customer
                    contact_formset.instance = customer

                    address_formset.save()
                    contact_formset.save()

                    messages.success(request, "Customer added successfully!")
                    return redirect("customer_list")
            else:
                messages.error(request, "Please correct the duplicate entry errors below.")

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        form = CustomerForm()
        address_formset = AddressFormSet(prefix="addresses")
        contact_formset = ContactFormSet(prefix="contacts")

    return render(
        request,
        "inventory/customer_form.html",
        {
            "form": form,
            "address_formset": address_formset,
            "contact_formset": contact_formset,
            "is_edit": False,
            "company": company  # ADD THIS
        },
    )


@login_required
def customer_edit(request, pk):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    customer = get_object_or_404(Customer, pk=pk, company=company)

    AddressFormSet = inlineformset_factory(
        Customer, Address, form=AddressForm, extra=0, can_delete=True
    )

    ContactFormSet = inlineformset_factory(
        Customer, ContactPerson, form=ContactPersonForm, extra=0, can_delete=True
    )

    if request.method == "POST":

        form = CustomerForm(request.POST, instance=customer)

        address_formset = AddressFormSet(
            request.POST,
            instance=customer,
            prefix="addresses"
        )

        contact_formset = ContactFormSet(
            request.POST,
            instance=customer,
            prefix="contacts"
        )

        if form.is_valid() and address_formset.is_valid() and contact_formset.is_valid():
            custom_has_error = False

            # --- 1. MAIN CUSTOMER VALIDATION ---
            email = form.cleaned_data.get('email')
            mobile = form.cleaned_data.get('mobile')
            gst_number = form.cleaned_data.get('gst_number')

            if email and Customer.objects.filter(company=company, email=email).exclude(pk=customer.pk).exists():
                form.add_error('email', 'A customer with this email already exists.')
                custom_has_error = True

            if mobile and Customer.objects.filter(company=company, mobile=mobile).exclude(pk=customer.pk).exists():
                form.add_error('mobile', 'A customer with this mobile number already exists.')
                custom_has_error = True

            if gst_number and Customer.objects.filter(company=company, gst_number=gst_number).exclude(pk=customer.pk).exists():
                form.add_error('gst_number', 'A customer with this GST number already exists.')
                custom_has_error = True

            # --- 2. CONTACT PERSON VALIDATION ---
            for c_form in contact_formset:
                if c_form.cleaned_data and not c_form.cleaned_data.get('DELETE', False):
                    c_email = c_form.cleaned_data.get('email')
                    c_phone = c_form.cleaned_data.get('phone') or c_form.cleaned_data.get('mobile')
                    
                    # Exclude the current contact instance if it already exists in DB
                    c_instance_pk = c_form.instance.pk if c_form.instance and c_form.instance.pk else None

                    if c_email:
                        qs = ContactPerson.objects.filter(customer__company=company, email=c_email)
                        if c_instance_pk:
                            qs = qs.exclude(pk=c_instance_pk)
                        if qs.exists():
                            c_form.add_error('email', 'A contact with this email already exists.')
                            custom_has_error = True
                    
                    if c_phone:
                        try:
                            qs = ContactPerson.objects.filter(customer__company=company, phone=c_phone)
                            if c_instance_pk: qs = qs.exclude(pk=c_instance_pk)
                            if qs.exists():
                                field_name = 'phone' if 'phone' in c_form.fields else 'mobile'
                                c_form.add_error(field_name, 'A contact with this phone already exists.')
                                custom_has_error = True
                        except: pass
                        
                        try:
                            qs = ContactPerson.objects.filter(customer__company=company, mobile=c_phone)
                            if c_instance_pk: qs = qs.exclude(pk=c_instance_pk)
                            if qs.exists():
                                field_name = 'mobile' if 'mobile' in c_form.fields else 'phone'
                                c_form.add_error(field_name, 'A contact with this mobile already exists.')
                                custom_has_error = True
                        except: pass

            # --- 3. ADDRESS VALIDATION ---
            for a_form in address_formset:
                if a_form.cleaned_data and not a_form.cleaned_data.get('DELETE', False):
                    a_email = a_form.cleaned_data.get('email')
                    a_phone = a_form.cleaned_data.get('phone') or a_form.cleaned_data.get('mobile')
                    
                    # Exclude the current address instance if it already exists in DB
                    a_instance_pk = a_form.instance.pk if a_form.instance and a_form.instance.pk else None

                    if a_email:
                        qs = Address.objects.filter(customer__company=company, email=a_email)
                        if a_instance_pk: qs = qs.exclude(pk=a_instance_pk)
                        if qs.exists():
                            a_form.add_error('email', 'An address with this email already exists.')
                            custom_has_error = True

                    if a_phone:
                        try:
                            qs = Address.objects.filter(customer__company=company, phone=a_phone)
                            if a_instance_pk: qs = qs.exclude(pk=a_instance_pk)
                            if qs.exists():
                                field_name = 'phone' if 'phone' in a_form.fields else 'mobile'
                                a_form.add_error(field_name, 'An address with this phone already exists.')
                                custom_has_error = True
                        except: pass
                        
                        try:
                            qs = Address.objects.filter(customer__company=company, mobile=a_phone)
                            if a_instance_pk: qs = qs.exclude(pk=a_instance_pk)
                            if qs.exists():
                                field_name = 'mobile' if 'mobile' in a_form.fields else 'phone'
                                a_form.add_error(field_name, 'An address with this mobile already exists.')
                                custom_has_error = True
                        except: pass

            if not custom_has_error:
                with transaction.atomic():

                    # save updated customer including website
                    customer = form.save(commit=False)
                    customer.company = company   # keep safe
                    customer.save()

                    address_formset.save()
                    contact_formset.save()

                    messages.success(request, "Customer updated successfully!")
                    return redirect("customer_list")

            else:
                messages.error(request, "Please correct the duplicate entry errors below.")

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        # THIS loads saved website value
        form = CustomerForm(instance=customer)

        address_formset = AddressFormSet(
            instance=customer,
            prefix="addresses"
        )

        contact_formset = ContactFormSet(
            instance=customer,
            prefix="contacts"
        )

    return render(
        request,
        "inventory/customer_form.html",
        {
            "form": form,
            "address_formset": address_formset,
            "contact_formset": contact_formset,
            "is_edit": True,
            "company": company
        },
    )


@login_required
def customer_delete(request, pk):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    customer = get_object_or_404(Customer, pk=pk, company=company)

    if request.method == "POST":
        with transaction.atomic():
            customer.delete()
            messages.error(request, "Customer deleted successfully.")
            return redirect("customer_list")

    return render(request, "inventory/customer_confirm_delete.html", {
        "customer": customer
    })



@login_required
def check_customer_field(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company   #  IMPORTANT

    field = request.GET.get('field')
    value = request.GET.get('value')
    
    if not field or not value:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    field_mapping = {
        'email': 'email',
        'gst_number': 'gst_number',
        'website': 'website',
    }
    
    if field not in field_mapping:
        return JsonResponse({'error': 'Invalid field'}, status=400)
    
    filter_kwargs = {f"{field_mapping[field]}__iexact": value}
    
    #  FIX HERE
    exists = Customer.objects.filter(
        company=company,
        **filter_kwargs
    ).exists()
    
    return JsonResponse({'exists': exists})




@login_required
def fast_slow_products_report(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    days = int(request.GET.get("days", 30))
    from_date = timezone.now() - timedelta(days=days)
    weeks = max(days / 7, 1)

    products = Product.objects.filter(company=company)

    report_data = []

    #  Counts for Cards
    fast_count = 0
    medium_count = 0
    slow_count = 0

    for product in products:
        sales_qs = SalesOrderItem.objects.filter(
            order__company=company,
            product=product,
            order__created_at__gte=from_date
        )

        total_qty = sales_qs.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        avg_weekly_sales = round(total_qty / weeks, 2)
        avg_daily_sales = total_qty / max(days, 1)

        if avg_daily_sales > 0:
            turnover_days = ceil(product.stock_quantity / avg_daily_sales)
        else:
            turnover_days = "-"

        # Velocity status + Count update
        if total_qty >= 10:
            status = "FAST"
            fast_count += 1

        elif total_qty > 0:
            status = "MEDIUM"
            medium_count += 1

        else:
            status = "SLOW"
            slow_count += 1

        report_data.append({
            "product": product,
            "avg_weekly_sales": avg_weekly_sales,
            "turnover_days": turnover_days,
            "status": status,
        })
    

    # Pagination
    paginator = Paginator(report_data, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/fast_slow_products.html",
        {
            "report_data": page_obj,        
            "page_obj": page_obj,           
            "company": company,

            # Dynamic Card Data
            "fast_count": fast_count,
            "medium_count": medium_count,
            "slow_count": slow_count,
        }
    )




@login_required
def export_inventory_velocity_xls(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    days = int(request.GET.get("days", 30))
    from_date = timezone.now() - timedelta(days=days)
    weeks = max(days / 7, 1)

    products = Product.objects.filter(company=company)

    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory Velocity"

    #  Header row
    ws.append([
        "Product Name",
        "SKU",
        "Category",
        "Avg Weekly Sales",
        "Turnover Days",
        "Status"
    ])

    for product in products:
        sales_qs = SalesOrderItem.objects.filter(
            order__company=company,
            product=product,
            order__created_at__gte=from_date
        )

        total_qty = sales_qs.aggregate(total=Sum("quantity"))["total"] or 0
        avg_weekly_sales = round(total_qty / weeks, 2)
        avg_daily_sales = total_qty / max(days, 1)

        turnover_days = ceil(product.stock_quantity / avg_daily_sales) if avg_daily_sales > 0 else "N/A"

        if total_qty >= 10:
            status = "FAST"
        elif total_qty > 0:
            status = "MEDIUM"
        else:
            status = "SLOW"

        ws.append([
            product.name,
            product.sku,
            product.category.name if product.category else "General",
            avg_weekly_sales,
            turnover_days,
            status
        ])

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="inventory_velocity_analysis.xlsx"'

    wb.save(response)
    return response


@login_required
def inventory_alerts(request):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    alerts_qs = InventoryAlert.objects.filter(
        company=company
    ).order_by("-created_at")

    paginator = Paginator(alerts_qs, 10)
    page_number = request.GET.get("page")
    alerts = paginator.get_page(page_number)

    critical_error_count = InventoryAlert.objects.filter(
        company=company,
        severity="HIGH"
    ).count()

    warnings_count = InventoryAlert.objects.filter(
        company=company,
        severity="MEDIUM"
    ).count()

    information_count = InventoryAlert.objects.filter(
        company=company,
        is_read=False
    ).count()

    return render(
        request,
        "inventory/inventory_alerts.html",
        {
            "alerts": alerts,
            "critical_error_count": critical_error_count,
            "warnings_count": warnings_count,
            "information_count": information_count,
            "company": company,   #  Missing this
        }
    )




@login_required
@require_POST
def mark_alerts_read(request):
    profile = UserProfile.objects.get(user=request.user)

    data = json.loads(request.body)
    alert_ids = data.get("alert_ids", [])

    InventoryAlert.objects.filter(
        id__in=alert_ids,
        company=profile.company
    ).update(is_read=True)

    return JsonResponse({"status": "success"})



@login_required
@transaction.atomic
def cancel_and_reverse_sales_order(request, pk):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    order = get_object_or_404(
        SalesOrder,
        id=pk,
        company=company
    )

    today = timezone.now().date()

    
    # STEP 1: RESTORE STOCK USING ORIGINAL SALE TRANSACTIONS
    
    sale_transactions = StockTransaction.objects.filter(
        company=company,
        transaction_type="OUT",
        source="SALE",
        reference_number=order.order_number
    ).select_related("batch", "product")

    for txn in sale_transactions:
        batch = txn.batch

        # Add quantity back to same batch
        batch.quantity += txn.quantity
        batch.save(update_fields=["quantity"])

    
    # STEP 2: RECONCILE PRODUCT STOCK
    
    products = order.items.values_list("product", flat=True)

    for product_id in products:
        product = Product.objects.get(id=product_id, company=company)

        product.stock_quantity = (
            ProductBatch.objects.filter(
                company=company,
                product=product,
                expiry_date__gte=today,
                quantity__gt=0,
                is_active=True
            ).aggregate(total=Sum("quantity"))["total"] or 0
        )

        product.save(update_fields=["stock_quantity"])

    
    # STEP 3: MARK ORDER CANCELLED
    
    order.status = "CANCELLED"
    order.save(update_fields=["status"])
    
    return redirect("sales_order_detail", pk=pk)




@login_required
def reorder_suggestions(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company
    search_query = request.GET.get("search", "").strip()
    days = int(request.GET.get("days", 30))
    from_date = timezone.now() - timedelta(days=days)

    products = Product.objects.filter(company=company)
    # 🔥 ADD THIS
    if search_query:
        products = products.filter(name__icontains=search_query)
    suggestions = []

    # NEW CARD VARIABLES
    predicted_volume = 0
    urgent_attention = 0
    healthy_products = 0

    for product in products:
        sales_qs = SalesOrderItem.objects.filter(
            order__company=company,
            product=product,
            order__created_at__gte=from_date
        )

        total_sold = sales_qs.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        avg_daily_sales = total_sold / max(days, 1)

        lead_time = 7
        safety_stock = product.low_stock_limit * 2

        reorder_level = ceil((avg_daily_sales * lead_time) + safety_stock)

        if product.stock_quantity <= reorder_level:
            reorder_qty = max(reorder_level - product.stock_quantity, 0)
            status = "REORDER"

            # CARD CALCULATIONS
            predicted_volume += reorder_qty
            urgent_attention += 1

        else:
            reorder_qty = 0
            status = "OK"
            healthy_products += 1

        suggestions.append({
            "product": product,
            "current_stock": product.stock_quantity,
            "avg_daily_sales": round(avg_daily_sales, 2),
            "reorder_level": reorder_level,
            "reorder_qty": reorder_qty,
            "status": status,
        })

    # STOCK HEALTH %
    total_products = len(products)
    stock_health = int((healthy_products / total_products) * 100) if total_products else 100

    # PAGINATION (unchanged)
    paginator = Paginator(suggestions, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/reorder_suggestions.html",
        {
            "suggestions": page_obj,
            "company": company,
            "days": days,
            
            "search_query": search_query,  #  ADD THIS
            # PASS CARD DATA
            "urgent_attention": urgent_attention,
            "predicted_volume": predicted_volume,
            "stock_health": stock_health,
        }
    )


@login_required
def get_batches_by_product(request):
    profile = UserProfile.objects.get(user=request.user)
    product_id = request.GET.get("product")

    batches = ProductBatch.objects.filter(
        company=profile.company,
        product_id=product_id,
        is_active=True
    ).values("batch_number", "quantity")

    return JsonResponse(list(batches), safe=False)


@login_required
@transaction.atomic
def delete_purchase_order(request, pk):
    profile = UserProfile.objects.get(user=request.user)

    order = get_object_or_404(
        PurchaseOrder,
        id=pk,
        company=profile.company
    )

    #  Safety: only DRAFT can be deleted
    if order.status != "DRAFT":
        messages.error(
            request,
            "Only draft purchase orders can be deleted."
        )
        return redirect("purchase_orders")

    order.delete()

    messages.success(
        request,
        "Draft purchase order deleted successfully."
    )

    return redirect("purchase_orders")


@login_required
def submit_purchase_order(request, pk):
    profile = UserProfile.objects.get(user=request.user)
    order = get_object_or_404(
        PurchaseOrder,
        id=pk,
        company=profile.company
    )

    if order.status != "DRAFT":
        return redirect("purchase_order_detail", pk=pk)

    order.status = "ORDERED"
    order.save(update_fields=["status"])

    messages.warning(request, "Draft purchase order saved successfully.")
    return redirect("purchase_order_detail", pk=pk)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date

from .models import Stock


from datetime import date
from django.contrib.auth.decorators import login_required

@login_required
def near_expiry_report(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company   #  IMPORTANT

    today = date.today()

    #  FILTER BY COMPANY
    stocks = Stock.objects.filter(
        company=company,                 
        expiry_date__isnull=False
    ).select_related("product")

    report = []
    expired_count = 0
    near_expiry_count = 0

    for stock in stocks:
        if stock.expiry_date < today:
            status = "Expired"
            expired_count += 1
        else:
            status = "Near Expiry"
            near_expiry_count += 1

        report.append({
            "product": stock.product.name,
            "batch": stock.batch_no,
            "expiry": stock.expiry_date,
            "quantity": stock.quantity,
            "status": status,
        })

    return render(
        request,
        "inventory/near_expiry_report.html",
        {
            "report": report,
            "expired_count": expired_count,
            "near_expiry_count": near_expiry_count,
            "total_items": len(report),
        }
    )



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from django.utils.timezone import now

from .models import Stock


class NearExpiryReportAPIView(APIView):
    """
    Returns Near-Expiry & Expired stock based only on expiry date
    (No threshold, no model changes)
    """
    renderer_classes = [JSONRenderer]

    def get(self, request):
        today = now().date()

        stocks = (
            Stock.objects
            .filter(expiry_date__isnull=False, quantity__gt=0)
            .order_by("expiry_date")  #  FEFO
        )

        expired = []
        near_expiry = []

        for stock in stocks:
            item = {
                "product": stock.product.name,
                "batch": stock.batch_no,
                "expiry_date": stock.expiry_date,
                "quantity": stock.quantity,
            }

            if stock.expiry_date < today:
                expired.append(item)
            else:
                near_expiry.append(item)

        return Response({
            "status": "success",
            "date": str(today),

            #  Counts for charts
            "summary": {
                "total_items": stocks.count(),
                "expired_count": len(expired),
                "near_expiry_count": len(near_expiry),
            },

            #  Data
            "expired_stock": expired,
            "near_expiry_stock": near_expiry,
        })



class PurchaseStockReportAPIView(APIView):
    def get(self, request):
        profile = UserProfile.objects.select_related("company").get(user=request.user)
        company = profile.company

        report_type = request.GET.get("report_type")
        date = request.GET.get("date")
        month = request.GET.get("month")
        product_id = request.GET.get("product_id")
        category_id = request.GET.get("category_id")

        queryset = PurchaseOrderItem.objects.select_related(
            "order", "product", "product__category"
        ).filter(
            order__company=company
        )

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if category_id:
            queryset = queryset.filter(product__category_id=category_id)

        if report_type == "daily":
            if date:
                queryset = queryset.filter(order__created_at__date=parse_date(date))

            data = (
                queryset
                .annotate(period=TruncDay("order__created_at"))
                .values(
                    "period",
                    product_name=F("product__name"),
                    category_name=F("product__category__name"),
                )
                .annotate(
                    total_quantity=Sum("quantity"),
                    total_amount=Sum(F("quantity") * F("cost_price")),
                )
                .order_by("period")
            )

        elif report_type == "monthly":
            if month:
                year, mon = month.split("-")
                queryset = queryset.filter(
                    order__created_at__year=year,
                    order__created_at__month=mon,
                )

            data = (
                queryset
                .annotate(period=TruncMonth("order__created_at"))
                .values(
                    "period",
                    product_name=F("product__name"),
                    category_name=F("product__category__name"),
                )
                .annotate(
                    total_quantity=Sum("quantity"),
                    total_amount=Sum(F("quantity") * F("cost_price")),
                )
                .order_by("period")
            )

        else:
            data = (
                queryset
                .annotate(period=TruncDay("order__created_at"))
                .values(
                    "period",
                    product_name=F("product__name"),
                    category_name=F("product__category__name"),
                )
                .annotate(
                    total_quantity=Sum("quantity"),
                    total_amount=Sum(F("quantity") * F("cost_price")),
                )
                .order_by("period")
            )

        return Response({
            "report_type": report_type,
            "count": len(data),
            "results": data,
        })



@login_required
def reports_view(request):
    """Enhanced reports view with stock report data"""
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    # Get date range from filters
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    
    # Orders table (sales) with date filtering
    orders_queryset = SalesOrder.objects.filter(company=company).order_by("-created_at")
    
    # Apply date filter if provided
    if from_date:
        orders_queryset = orders_queryset.filter(created_at__date__gte=from_date)
    if to_date:
        orders_queryset = orders_queryset.filter(created_at__date__lte=to_date)

    # Pagination logic (10 per page)
    paginator = Paginator(orders_queryset, 10)
    page_number = request.GET.get("page")
    orders = paginator.get_page(page_number)

    # SALES DATA (Monthly)
    sales_query = SalesOrder.objects.filter(company=company)
    if from_date:
        sales_query = sales_query.filter(created_at__date__gte=from_date)
    if to_date:
        sales_query = sales_query.filter(created_at__date__lte=to_date)
    
    sales_data = (
        sales_query
        .values("created_at__month")
        .annotate(total=Sum("total_amount"))
        .order_by("created_at__month")
    )
    
    # PURCHASE DATA (Monthly)
    
    purchase_query = PurchaseOrder.objects.filter(company=company)   

    if from_date:
        purchase_query = purchase_query.filter(created_at__date__gte=from_date)

    if to_date: 
        purchase_query = purchase_query.filter(created_at__date__lte=to_date)

    purchase_data = (
        purchase_query
        .values("created_at__month")
        .annotate(total=Sum("total_amount"))
        .order_by("created_at__month")
    )
    
    # MERGE MONTHS
    
    months = sorted(
        set(
            [s["created_at__month"] for s in sales_data] +
            [p["created_at__month"] for p in purchase_data]
        )
    )

    chart_labels = [
        timezone.now().replace(month=m).strftime("%b") for m in months
    ]

    sales_totals = [
        float(next((s["total"] for s in sales_data if s["created_at__month"] == m), 0))
        for m in months
    ]

    purchase_totals = [
        float(next((p["total"] for p in purchase_data if p["created_at__month"] == m), 0))
        for m in months
    ]

    
    # DAILY/MONTHLY STOCK REPORT DATA
    
    
    # Today's date
    today = timezone.now().date()
    
    # Get today's purchases
    today_purchases = PurchaseOrderItem.objects.filter(
        order__company=company,
        order__created_at__date=today
    ).select_related('product', 'product__category')
    
    # Today's summary - FIXED: Add output_field for multiplication
    today_summary = today_purchases.aggregate(
        total_quantity=Coalesce(Sum('quantity'), Value(0)),
        total_amount=Coalesce(
            Sum(F('quantity') * F('cost_price'), output_field=DecimalField(max_digits=12, decimal_places=2)),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )
    
    # Monthly summary (current month)
    current_month = today.replace(day=1)
    monthly_purchases = PurchaseOrderItem.objects.filter(
        order__company=company,
        order__created_at__date__gte=current_month
    )
    
    monthly_summary = monthly_purchases.aggregate(
        total_quantity=Coalesce(Sum('quantity'), Value(0)),
        total_amount=Coalesce(
            Sum(F('quantity') * F('cost_price'), output_field=DecimalField(max_digits=12, decimal_places=2)),
            Value(0, output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )
    
    # Calculate average daily purchase for current month
    days_in_month = today.day
    
    # Get the monthly amount
    monthly_amount = monthly_summary.get('total_amount', 0)
    if monthly_amount is None:
        monthly_amount = 0
    
    # Calculate average (handle division by zero)
    if days_in_month > 0 and monthly_amount:
        avg_daily = monthly_amount / days_in_month
    else:
        avg_daily = 0
    
    # Count active products
    active_products = Product.objects.filter(
        company=company,
        stock_quantity__gt=0
    ).count()
    
    # Get recent purchases (last 5)
    recent_purchases_list = PurchaseOrderItem.objects.filter(
        order__company=company
    ).select_related('product', 'product__category', 'order').order_by('-order__created_at')[:5]
    
    # Format recent purchases
    recent_purchases = []
    for item in recent_purchases_list:
        # Handle None values
        quantity = item.quantity if item.quantity is not None else 0
        cost_price = item.cost_price if item.cost_price is not None else 0
        
        recent_purchases.append({
            'date': item.order.created_at,
            'product_name': item.product.name,
            'category_name': item.product.category.name if item.product.category else None,
            'quantity': quantity,
            'amount': float(quantity * cost_price)
        })

    context = {
        "company": company,
        "orders": orders,
        "chart_labels": chart_labels,
        "sales_data": sales_totals,
        "purchase_data": purchase_totals,
        
        # Stock report data
        "today": today.strftime('%Y-%m-%d'),
        "current_month": today.strftime('%Y-%m'),
        "today_data": {
            "total_quantity": float(today_summary.get('total_quantity', 0)),
            "total_amount": float(today_summary.get('total_amount', 0))
        },
        "monthly_data": {
            "total_quantity": float(monthly_summary.get('total_quantity', 0)),
            "total_amount": float(monthly_summary.get('total_amount', 0))
        },
        "avg_daily": float(avg_daily),
        "active_products": active_products,
        "recent_purchases": recent_purchases,
    }

    return render(request, "inventory/report.html", context)


@login_required
def purchase_stock_report_view(request):
    """
    View for the purchase stock report frontend
    This shows the detailed purchase stock report page
    """
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company
    
    # Get query parameters
    report_type = request.GET.get('report_type', 'daily')
    
    return render(
        request,
        "inventory/purchase_stock_report.html",
        {
            "company": company,
            "report_type": report_type,
        }
    )




@login_required
def products_list_api(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    products = Product.objects.filter(company=company).values("id", "name")

    return JsonResponse(list(products), safe=False)

@login_required
def categories_list_api(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    categories = Category.objects.filter(company=company).values("id", "name")

    return JsonResponse(list(categories), safe=False)




class NearExpiryProductReportView(APIView):
    """
    API to get near-expiry products.
    Filters:
      - days (default 10)
      - product_id
      - category_id
    """

    def get(self, request):
        # 1️Get query params
        try:
            days = int(request.GET.get('days', 10))
        except ValueError:
            return Response({"error": "Days must be a number"}, status=status.HTTP_400_BAD_REQUEST)

        if days < 1:
            return Response({"error": "Days must be >= 1"}, status=status.HTTP_400_BAD_REQUEST)

        product_id = request.GET.get('product_id')
        category_id = request.GET.get('category_id')

        #  Calculate expiry limit
        today = date.today()
        expiry_limit = today + timedelta(days=days)

        #  Build queryset
        queryset = ProductBatch.objects.filter(
            is_active=True,
            expiry_date__range=(today, expiry_limit)
        ).select_related('product', 'product__category')

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if category_id:
            queryset = queryset.filter(product__category_id=category_id)

        #  No records found
        if not queryset.exists():
            return Response({"message": "No near-expiry products found"}, status=status.HTTP_200_OK)

        #  Prepare response
        data = []
        for batch in queryset:
            days_left = (batch.expiry_date - today).days if batch.expiry_date else None
            data.append({
                "product": batch.product.name,
                "category": batch.product.category.name if batch.product.category else None,
                "batch_number": batch.batch_number,
                "expiry_date": batch.expiry_date,
                "days_left": days_left,
                "quantity": batch.quantity
            })

        return Response({
            "total": queryset.count(),
            "days_filter": days,
            "results": data
        }, status=status.HTTP_200_OK)


@login_required
def near_expiry_report_view(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company   #  IMPORTANT

    today_date = date.today()
    days = int(request.GET.get('days', 30))
    product_id = request.GET.get('product_id', '')

    #  ONLY COMPANY PRODUCTS
    products = list(
        Product.objects.filter(company=company).order_by('name')
    )

    #  ONLY COMPANY BATCHES
    batches = ProductBatch.objects.filter(
        company=company,             
        quantity__gt=0,
        expiry_date__isnull=False
    ).select_related("product").order_by('expiry_date')

    #  SAFE PRODUCT FILTER
    if product_id:
        batches = batches.filter(
            product_id=product_id,
            product__company=company   #  EXTRA SAFETY
        )

    #  FILTER BY EXPIRY DAYS
    end_date = today_date + timedelta(days=days)

    batches = batches.filter(
        expiry_date__lte=end_date,
        expiry_date__gte=today_date
    )

    batches = list(batches)[:100]

    table_data = []
    status_counts = {'critical': 0, 'warning': 0, 'caution': 0}

    for batch in batches:
        days_left = (batch.expiry_date - today_date).days

        if days_left <= 3:
            status = 'CRITICAL'
            status_counts['critical'] += 1
        elif days_left <= 7:
            status = 'WARNING'
            status_counts['warning'] += 1
        else:
            status = 'CAUTION'
            status_counts['caution'] += 1

        table_data.append({
            'product': batch.product.name,
            'category': batch.product.category.name if batch.product.category else 'N/A',
            'batch_number': batch.batch_number or 'NO-BATCH',
            'expiry_date': batch.expiry_date,
            'days_left': days_left,
            'quantity': batch.quantity,
            'status': status,
        })

    context = {
        'products': products,
        'days': days,
        'selected_product': product_id,
        'table_data': table_data,
        'total_items': len(table_data),
        'status_counts': status_counts,
        'chart_title': f'Near Expiry ({days} days | {len(table_data)} batches)',
        'company':company,
    }

    return render(request, "inventory/near_expiry_report.html", context)
      



# FAST & SLOW MOVING PRODUCTS – SHARED DATA FUNCTION
def get_fast_slow_products_data(request):
    # Get logged-in company (MANDATORY)
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    
    # GET FILTER PARAMETERS
    purchase_from = request.GET.get("purchase_from")
    purchase_to = request.GET.get("purchase_to")
    sale_from = request.GET.get("sale_from")
    sale_to = request.GET.get("sale_to")

    category_id = request.GET.get("category")
    status_filter = request.GET.get("status")

    # SAFE DATE CONVERSION (FIX)
    if purchase_from:
        purchase_from = date.fromisoformat(purchase_from)

    if purchase_to:
        purchase_to = date.fromisoformat(purchase_to)

    if sale_from:
        sale_from = date.fromisoformat(sale_from)

    if sale_to:
        sale_to = date.fromisoformat(sale_to)


    # COMPANY-WISE PRODUCTS ONLY
    products = Product.objects.filter(company=company)

    if category_id:
        products = products.filter(category_id=category_id)

    today = now().date()
    slow_threshold = today - timedelta(days=30)

    results = []

    for p in products:
        # LAST PURCHASE (STOCK IN)
        last_purchase = (
            p.stocktransaction_set
            .filter(company=company, transaction_type="IN")
            .aggregate(d=Max("created_at"))["d"]
        )

        # LAST SALE (STOCK OUT)
        last_sale = (
            p.stocktransaction_set
            .filter(company=company, transaction_type="OUT")
            .aggregate(d=Max("created_at"))["d"]
        )


        # FAST / SLOW LOGIC
        status = (
            "FAST"
            if last_sale and last_sale.date() >= slow_threshold
            else "SLOW"
        )

        # STATUS FILTER
        if status_filter and status != status_filter:
            continue

        # PURCHASE DATE FILTERS
        if purchase_from and last_purchase and last_purchase.date() < purchase_from:
            continue

        if purchase_to and last_purchase and last_purchase.date() > purchase_to:
            continue


        # SALE DATE FILTERS
        if sale_from and last_sale and last_sale.date() < sale_from:
            continue

        if sale_to and last_sale and last_sale.date() > sale_to:
            continue

        # FINAL ROW
        results.append({
            "product": p.name,
            "category": p.category.name if p.category else "N/A",
            "purchase_date": last_purchase.date() if last_purchase else None,
            "sale_date": last_sale.date() if last_sale else None,
            "status": status,
        })

    return results


# FAST & SLOW PRODUCTS API
def fast_slow_products_api(request):
    """
    JSON API used by UI / AJAX
    """
    data = get_fast_slow_products_data(request)
    return JsonResponse({"results": data})


@login_required
def fast_slow_products_view(request):
    profile = UserProfile.objects.select_related(
        "company"
    ).get(user=request.user)

    company = profile.company

    products_list = get_fast_slow_products_data(
        request
    )

    categories = Category.objects.filter(
        company=company
    )

    # Pagination (10 per page)
    paginator = Paginator(
        products_list,
        10
    )

    page_number = request.GET.get(
        "page"
    )

    # safer handling
    products = paginator.get_page(
        page_number
    )

    return render(
        request,
        "inventory/fastslow_products.html",
        {
            "products": products,
            "page_obj": products,
            "categories": categories,
            "company": company,
        }
    )


@login_required
def profit_margin_report_api(request):
    # Logged-in company
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    category_id = request.GET.get("category")
    period = request.GET.get("period")  # day | month | year

    today = timezone.now().date()

    # Date range
    if period == "day":
        from_date = today
    elif period == "month":
        from_date = today.replace(day=1)
    elif period == "year":
        from_date = today.replace(month=1, day=1)
    else:
        from_date = today.replace(month=1, day=1)  # default = year

    # Products (company-wise)
    products = Product.objects.filter(company=company)

    if category_id:
        products = products.filter(category_id=category_id)

    results = []

    for product in products:
        sales_items = SalesOrderItem.objects.filter(
            order__company=company,
            product=product,
            order__created_at__date__gte=from_date
        )

        total_qty = sales_items.aggregate(
            total=Sum("quantity")
        )["total"] or 0

        purchase_price = product.purchase_price or 0
        selling_price = product.selling_price or 0

        profit_per_unit = selling_price - purchase_price
        total_profit = profit_per_unit * total_qty

        results.append({
            "product": product.name,
            "purchase_price": purchase_price,
            "selling_price": selling_price,
            "quantity_sold": total_qty,
            "profit": total_profit if total_profit > 0 else 0,
            "loss": abs(total_profit) if total_profit < 0 else 0,
        })

    return JsonResponse({"results": results})


from datetime import date
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum


@login_required
def profit_margin_report_view(request):
    profile = UserProfile.objects.select_related(
        "company"
    ).get(user=request.user)

    company = profile.company

    category_id = request.GET.get("category")
    product_id = request.GET.get("product")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")


    # ---------- SAFE PARAM CLEANING ----------
    def safe_int(value):
        try:
            if value and value not in ["", "None"]:
                return int(value)
        except ValueError:
            return None
        return None


    category_id = safe_int(category_id)
    product_id = safe_int(product_id)


    # ---------- BASE QUERY ----------
    items = SalesOrderItem.objects.filter(
        order__company=company,
        order__status="DELIVERED"
    )


    # ---------- DATE FILTER ----------
    parsed_from = None
    parsed_to = None

    if from_date:
        try:
            parsed_from = date.fromisoformat(from_date)
            items = items.filter(
                order__created_at__date__gte=parsed_from
            )
        except Exception:
            parsed_from = None

    if to_date:
        try:
            parsed_to = date.fromisoformat(to_date)
            items = items.filter(
                order__created_at__date__lte=parsed_to
            )
        except Exception:
            parsed_to = None


    # overwrite for template
    from_date = parsed_from
    to_date = parsed_to


    # ---------- FILTERS ----------
    if category_id:
        items = items.filter(
            product__category_id=category_id
        )

    if product_id:
        items = items.filter(
            product_id=product_id
        )


    # ---------- PRODUCTS ----------
    products = Product.objects.filter(
        company=company
    )

    if category_id:
        products = products.filter(
            category_id=category_id
        )

    if product_id:
        products = products.filter(
            id=product_id
        )


    # ---------- AGGREGATION (OPTIMIZED) ----------
    sales_data = (
        items.values("product")
        .annotate(
            total_qty=Sum("quantity")
        )
    )

    sales_map = {
        entry["product"]: entry["total_qty"]
        for entry in sales_data
    }


    # ---------- BUILD REPORT ----------
    rows = []

    for product in products:
        sold_qty = sales_map.get(
            product.id,
            0
        )

        if sold_qty == 0:
            continue

        purchase_price = product.purchase_price or 0
        selling_price = product.selling_price or 0

        profit_value = (
            selling_price - purchase_price
        ) * sold_qty

        rows.append({
            "product": product.name,
            "purchase_price": purchase_price,
            "selling_price": selling_price,
            "qty": sold_qty,
            "profit": (
                profit_value
                if profit_value > 0
                else 0
            ),
            "loss": (
                abs(profit_value)
                if profit_value < 0
                else 0
            ),
        })


    # ---------- SORT (Optional) ----------
    rows = sorted(
        rows,
        key=lambda x: x["profit"],
        reverse=True
    )


    # ---------- PAGINATION ----------
    paginator = Paginator(
        rows,
        10  # rows per page
    )

    page_number = request.GET.get("page")
    rows = paginator.get_page(
        page_number
    )


    return render(
        request,
        "inventory/profit_margin_report.html",
        {
            "company": company,
            "categories": Category.objects.filter(
                company=company
            ),
            "products": products,
            "rows": rows,  # paginated rows
            "selected_category": category_id,
            "selected_product": product_id,
            "from_date": from_date,
            "to_date": to_date,
        }
    )

@login_required
def products_by_category_api(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)
    company = profile.company

    category_id = request.GET.get("category")

    products = Product.objects.filter(company=company)

    if category_id:
        products = products.filter(category_id=category_id)

    data = {
        "products": [
            {"id": p.id, "name": p.name}
            for p in products.order_by("name")
        ]
    }

    return JsonResponse(data)




@login_required
def supplier_performance(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company   #  IMPORTANT

    supplier_id = request.GET.get('supplier')

    table_data = []

    #  ONLY COMPANY VENDORS
    all_vendors = Vendor.objects.filter(company=company)

    dropdown_suppliers = []

    for vendor in all_vendors:
        total_orders = vendor.purchaseorder_set.filter(company=company).count()

        supplier_name = (
            getattr(vendor, 'display_name', None) or
            f"{vendor.first_name or ''} {vendor.last_name or ''}".strip() or
            vendor.company_name or
            f"Supplier #{vendor.id}"
        )

        dropdown_suppliers.append({
            'id': vendor.id,
            'name': supplier_name,
            'total_orders': total_orders,
        })

    
    # FILTERED TABLE DATA
    
    if supplier_id:
        vendor = Vendor.objects.filter(id=supplier_id, company=company).first()

        if vendor:
            total_orders = vendor.purchaseorder_set.filter(company=company).count()

            supplier_name = (
                getattr(vendor, 'display_name', None) or
                f"{vendor.first_name or ''} {vendor.last_name or ''}".strip() or
                vendor.company_name or
                f"Supplier #{vendor.id}"
            )

            if total_orders == 0:
                on_time_rate = 0
                defect_rate = 0
                total_value = 0
                avg_lead_time = 0
                score = 0
            else:
                on_time_rate = round(95 - (total_orders * 2), 1)
                defect_rate = round(2 + (total_orders * 0.5), 1)
                total_value = total_orders * 75000
                avg_lead_time = round(5 + total_orders * 0.5, 1)
                score = max(70, min(98, 95 - total_orders * 3))

            table_data.append({
                'id': vendor.id,
                'name': supplier_name,
                'email': vendor.email or 'N/A',
                'total_orders': total_orders,
                'on_time_rate': on_time_rate,
                'defect_rate': defect_rate,
                'total_value': total_value,
                'avg_lead_time': avg_lead_time,
                'score': score,
            })
    else:
        # ALL SUPPLIERS (COMPANY ONLY)
        for vendor in all_vendors:

            total_orders = vendor.purchaseorder_set.filter(company=company).count()

            supplier_name = (
                getattr(vendor, 'display_name', None) or
                f"{vendor.first_name or ''} {vendor.last_name or ''}".strip() or
                vendor.company_name or
                f"Supplier #{vendor.id}"
            )

            if total_orders == 0:
                on_time_rate = 0
                defect_rate = 0
                total_value = 0
                avg_lead_time = 0
                score = 0
            else:
                on_time_rate = round(95 - (total_orders * 2), 1)
                defect_rate = round(2 + (total_orders * 0.5), 1)
                total_value = total_orders * 75000
                avg_lead_time = round(5 + total_orders * 0.5, 1)
                score = max(70, min(98, 95 - total_orders * 3))

            table_data.append({
                'id': vendor.id,
                'name': supplier_name,
                'email': vendor.email or 'N/A',
                'total_orders': total_orders,
                'on_time_rate': on_time_rate,
                'defect_rate': defect_rate,
                'total_value': total_value,
                'avg_lead_time': avg_lead_time,
                'score': score,
            })

    
    # CHART DATA
    
    if supplier_id and table_data:
        chart_labels = [table_data[0]['name'][:12]]
        on_time_data = [table_data[0]['on_time_rate']]
        defect_data = [table_data[0]['defect_rate']]
        chart_title = f"{table_data[0]['name'][:20]} Performance"
    else:
        chart_labels = [s['name'][:12] for s in table_data[:10]]
        on_time_data = [s['on_time_rate'] for s in table_data[:10]]
        defect_data = [s['defect_rate'] for s in table_data[:10]]
        chart_title = "All Suppliers Overview"

    context = {
        'suppliers': dropdown_suppliers,
        'table_data': table_data,
        'total_suppliers': len(dropdown_suppliers),
        'selected_supplier': supplier_id,
        'chart_labels': json.dumps(chart_labels),
        'on_time_data': json.dumps(on_time_data),
        'defect_data': json.dumps(defect_data),
        'selected_supplier_name': table_data[0]['name'] if supplier_id and table_data else 'All Suppliers',
        'chart_title': chart_title,
        'company':company,
    }

    return render(request, 'inventory/supplier_performance.html', context)



@login_required
def expired_stock_report(request):

    #  GET COMPANY
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    category_filter = request.GET.get('category', 'all')

    today = timezone.now().date()

    #  COMPANY FILTER ADDED HERE
    batches = ProductBatch.objects.filter(
        company=company,
        expiry_date__lt=today,
        is_active=True
    ).select_related("product", "product__category")

    #  CATEGORY FILTER
    if category_filter != 'all':
        batches = batches.filter(product__category_id=category_filter)

    #  COMPANY CATEGORIES FOR DROPDOWN
    categories = Category.objects.filter(company=company)

    category_counts = defaultdict(int)
    expired_data = []

    batches_list = list(batches)  # needed for index()

    for batch in batches_list:

        # PRIORITY 1: StockTransaction reference_number
        txn = StockTransaction.objects.filter(
            batch=batch,
            source="PURCHASE",
            transaction_type="IN",
            reference_number__isnull=False,
            reference_number__gt=''
        ).order_by("-created_at").first()

        po_no = txn.reference_number if txn and txn.reference_number else None

        # PRIORITY 2: PurchaseOrder.order_number
        if not po_no:
            po = PurchaseOrder.objects.filter(
                company=company,
                status="RECEIVED",
                order_number__isnull=False,
                order_number__gt=''
            ).order_by("-created_at")[:10]

            po_index = batches_list.index(batch) % len(po) if po else 0
            po_no = po[po_index].order_number if po and po_index < len(po) else None

        # FINAL FALLBACK
        final_po_no = po_no or f"PO-{batch.id:03d}"

        category_name = getattr(batch.product.category, 'name', 'Uncategorized') or 'Uncategorized'
        category_counts[category_name] += 1

        expired_data.append({
            'product': batch.product.name,
            'category': category_name,
            'batch_no': batch.batch_number or "NO-BATCH",
            'purchase_order_no': final_po_no,
            'expiry_date': batch.expiry_date,
            'total_stock': float(batch.quantity or 0),
            'total_amount': float((batch.quantity or 0) * 150)
        })

    chart_labels = list(category_counts.keys())[:5]
    chart_data = [category_counts[label] for label in chart_labels]

    context = {
        'expired_data': expired_data,
        'total_expired': len(expired_data),
        'selected_category': category_filter,
        'company': company,
        'categories': categories,   #  IMPORTANT FOR DROPDOWN
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }

    return render(request, "inventory/expired_stock_report.html", context)



def inventory_history(request): 
    return render(request, 'inventory/product_list.html')


@login_required
def inventory_history(request, pk):
    company = owner_required(request)
    if not company:
        return redirect("company_login")

    product = get_object_or_404(Product, id=pk, company=company)

    # Base queryset
    transactions = StockTransaction.objects.filter(
        company=company,
        product=product
    ).order_by("-created_at")

    # Advanced Filters
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    flow_type = request.GET.get("flow_type")

    if from_date:
        transactions = transactions.filter(created_at__date__gte=from_date)

    if to_date:
        transactions = transactions.filter(created_at__date__lte=to_date)

    if flow_type:
        transactions = transactions.filter(transaction_type=flow_type)

    current_month = now().month
    current_year = now().year

    monthly_data = StockTransaction.objects.filter(
        company=company,
        product=product,
        created_at__year=current_year,
        created_at__month=current_month
    )

    monthly_stock_in = monthly_data.filter(
        transaction_type="IN"
    ).aggregate(total=Sum("quantity"))["total"] or 0

    monthly_stock_out = monthly_data.filter(
        transaction_type="OUT"
    ).aggregate(total=Sum("quantity"))["total"] or 0

    net_velocity = monthly_stock_in - monthly_stock_out

    paginator = Paginator(transactions, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "transactions": page_obj,
        "page_obj": page_obj,
        "company": company,
        "product": product,
        "monthly_stock_in": monthly_stock_in,
        "monthly_stock_out": monthly_stock_out,
        "net_velocity": net_velocity,
    }

    return render(request, "company/stock_movement_report.html", context)
    





@login_required
def batch_stock(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    batches = get_batch_stock_queryset(request, company)

    paginator = Paginator(batches, 5)  # keep small number to test
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "inventory/batch_stock.html", {
        "page_obj": page_obj,
        "company": company,
    })


# 1. CURRENT STOCK SUMMARY API
class StockSummaryAPIView(APIView):
    """
    API: GET /api/stock/summary/
    Returns current stock summary (product-wise, category-wise)
    """
    
    @method_decorator(login_required)
    def get(self, request):
        profile = UserProfile.objects.select_related("company").get(user=request.user)
        company = profile.company
        
        # Get filters
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        low_stock_only = request.GET.get('low_stock_only', 'false').lower() == 'true'
        
        # Base queryset
        products = Product.objects.filter(company=company)
        
        # Apply filters
        if category_id:
            products = products.filter(category_id=category_id)
        if product_id:
            products = products.filter(id=product_id)
        if low_stock_only:
            products = products.filter(stock_quantity__lte=F('low_stock_limit'))
        
        # Get batch stock info
        today = date.today()
        summary_data = []
        
        for product in products:
            # Calculate available stock from non-expired batches
            available_stock = (
                ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=today,
                    quantity__gt=0,
                    is_active=True
                ).aggregate(total=Sum('quantity'))['total'] or 0
            )
            
            # Calculate reserved stock (from pending sales orders)
            reserved_stock = (
                SalesOrderItem.objects.filter(
                    order__company=company,
                    product=product,
                    order__status__in=['PENDING', 'PROCESSING']
                ).aggregate(total=Sum('quantity'))['total'] or 0
            )
            
            summary_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'category': product.category.name if product.category else 'Uncategorized',
                'category_id': product.category.id if product.category else None,
                'sku': product.sku,
                'available_stock': available_stock,
                'reserved_stock': reserved_stock,
                'total_stock': available_stock + reserved_stock,
                'low_stock_limit': product.low_stock_limit,
                'is_low_stock': available_stock <= product.low_stock_limit,
                'purchase_price': float(product.purchase_price),
                'selling_price': float(product.selling_price),
                'stock_value': float(available_stock * product.purchase_price),
                'selling_value': float(available_stock * product.selling_price),
            })
        
        # Category-wise summary
        category_summary = {}
        for item in summary_data:
            cat = item['category']
            if cat not in category_summary:
                category_summary[cat] = {
                    'total_products': 0,
                    'total_stock': 0,
                    'total_value': 0,
                    'low_stock_count': 0
                }
            
            category_summary[cat]['total_products'] += 1
            category_summary[cat]['total_stock'] += item['available_stock']
            category_summary[cat]['total_value'] += item['stock_value']
            if item['is_low_stock']:
                category_summary[cat]['low_stock_count'] += 1
        
        return Response({
            'status': 'success',
            'company': company.name,
            'total_products': len(summary_data),
            'total_stock': sum(item['available_stock'] for item in summary_data),
            'total_value': sum(item['stock_value'] for item in summary_data),
            'low_stock_count': sum(1 for item in summary_data if item['is_low_stock']),
            'category_summary': category_summary,
            'product_summary': summary_data
        })

# 2. AVAILABLE VS RESERVED STOCK API
class AvailableVsReservedStockAPIView(APIView):
    """
    API: GET /api/stock/available-vs-reserved/
    Returns available stock vs reserved stock comparison
    """
    
    @method_decorator(login_required)
    def get(self, request):
        profile = UserProfile.objects.select_related("company").get(user=request.user)
        company = profile.company
        
        # Get filters
        product_id = request.GET.get('product_id')
        category_id = request.GET.get('category_id')
        
        today = date.today()
        
        # Get products
        products = Product.objects.filter(company=company)
        if category_id:
            products = products.filter(category_id=category_id)
        if product_id:
            products = products.filter(id=product_id)
        
        result = []
        total_available = 0
        total_reserved = 0
        
        for product in products:
            # Available stock (non-expired batches)
            available_stock = (
                ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=today,
                    quantity__gt=0,
                    is_active=True
                ).aggregate(total=Sum('quantity'))['total'] or 0
            )
            
            # Reserved stock (pending sales orders)
            reserved_stock = (
                SalesOrderItem.objects.filter(
                    order__company=company,
                    product=product,
                    order__status__in=['PENDING', 'PROCESSING']
                ).aggregate(total=Sum('quantity'))['total'] or 0
            )
            
            # Calculate utilization percentage
            total_stock = available_stock + reserved_stock
            if total_stock > 0:
                available_percent = (available_stock / total_stock) * 100
                reserved_percent = (reserved_stock / total_stock) * 100
            else:
                available_percent = reserved_percent = 0
            
            result.append({
                'product_id': product.id,
                'product_name': product.name,
                'category': product.category.name if product.category else 'Uncategorized',
                'available_stock': available_stock,
                'reserved_stock': reserved_stock,
                'total_stock': total_stock,
                'available_percent': round(available_percent, 2),
                'reserved_percent': round(reserved_percent, 2),
                'status': 'HIGH_DEMAND' if reserved_percent > 50 else 'NORMAL'
            })
            
            total_available += available_stock
            total_reserved += reserved_stock
        
        # Overall summary
        overall_total = total_available + total_reserved
        if overall_total > 0:
            overall_available_percent = (total_available / overall_total) * 100
            overall_reserved_percent = (total_reserved / overall_total) * 100
        else:
            overall_available_percent = overall_reserved_percent = 0
        
        return Response({
            'status': 'success',
            'company': company.name,
            'total_available_stock': total_available,
            'total_reserved_stock': total_reserved,
            'overall_total_stock': overall_total,
            'overall_available_percent': round(overall_available_percent, 2),
            'overall_reserved_percent': round(overall_reserved_percent, 2),
            'products': result
        })


class ExpiryWiseStockAPIView(APIView):
    """
    API: GET /api/stocks/expiry-wise/
    Returns batch-wise stock sorted by expiry date (FEFO)
    Uses ProductBatch model which has expiry_date field
    """
    
    def get(self, request):
        today = now().date()
        
        # Get user's company
        try:
            profile = UserProfile.objects.select_related("company").get(user=request.user)
            company = profile.company
        except UserProfile.DoesNotExist:
            return Response({"error": "Authentication required"}, status=401)
        
        # Use ProductBatch model instead of Stock
        batches = ProductBatch.objects.filter(
            company=company,
            quantity__gt=0,
            is_active=True,
            expiry_date__isnull=False
        ).select_related("product", "product__category").order_by("expiry_date")
        
        # Prepare data
        data = []
        expired_count = 0
        expiring_soon_count = 0
        near_expiry_limit = today + timedelta(days=30)
        
        for batch in batches:
            days_left = (batch.expiry_date - today).days
            
            # Count status
            if batch.expiry_date < today:
                status = "EXPIRED"
                status_class = "text-danger"
                expired_count += 1
            elif batch.expiry_date <= near_expiry_limit:
                status = "NEAR EXPIRY"
                status_class = "text-warning"
                expiring_soon_count += 1
            else:
                status = "SAFE"
                status_class = "text-success"
            
            data.append({
                "id": batch.id,
                "product_id": batch.product.id,
                "product_name": batch.product.name,
                "sku": batch.product.sku,
                "category": batch.product.category.name if batch.product.category else "Uncategorized",
                "batch_number": batch.batch_number or "NO-BATCH",
                "expiry_date": batch.expiry_date,
                "expiry_date_formatted": batch.expiry_date.strftime("%d %b %Y"),
                "quantity": batch.quantity,
                "days_left": days_left,
                "status": status,
                "status_class": status_class,
            })
        
        return Response({
            "status": "success",
            "company": company.name,
            "today": str(today),
            "today_formatted": today.strftime("%d %b %Y"),
            "summary": {
                "total_batches": len(data),
                "expired_count": expired_count,
                "expiring_soon_count": expiring_soon_count,
                "safe_count": len(data) - expired_count - expiring_soon_count,
            },
            "data": data,
        })
    
class StockValuationAPIView(APIView):
    """
    API: GET /api/stocks/valuation/
    Returns stock valuation based on purchase price & quantity from batches
    Uses ProductBatch and Product models (not empty Stock model)
    """
    
    def get(self, request):
        # Get user's company
        try:
            profile = UserProfile.objects.select_related("company").get(user=request.user)
            company = profile.company
        except UserProfile.DoesNotExist:
            return Response({"error": "Authentication required"}, status=401)
        
        today = date.today()
        
        # Get all active batches with quantity > 0
        batches = ProductBatch.objects.filter(
            company=company,
            quantity__gt=0,
            is_active=True,
            expiry_date__gte=today  # Only non-expired stock for valuation
        ).select_related("product")
        
        # Group by product for product-wise valuation
        product_valuation = {}
        
        for batch in batches:
            product_id = batch.product.id
            product_name = batch.product.name
            sku = batch.product.sku
            category = batch.product.category.name if batch.product.category else "Uncategorized"
            purchase_price = float(batch.product.purchase_price or 0)
            selling_price = float(batch.product.selling_price or 0)
            quantity = batch.quantity
            
            if product_id not in product_valuation:
                product_valuation[product_id] = {
                    "product_id": product_id,
                    "product_name": product_name,
                    "sku": sku,
                    "category": category,
                    "purchase_price": purchase_price,
                    "selling_price": selling_price,
                    "total_quantity": 0,
                    "total_purchase_value": 0,
                    "total_selling_value": 0,
                    "batches": []
                }
            
            product_valuation[product_id]["total_quantity"] += quantity
            product_valuation[product_id]["total_purchase_value"] += quantity * purchase_price
            product_valuation[product_id]["total_selling_value"] += quantity * selling_price
            product_valuation[product_id]["batches"].append({
                "batch_number": batch.batch_number or "NO-BATCH",
                "expiry_date": batch.expiry_date,
                "quantity": batch.quantity,
                "purchase_price": purchase_price,
                "selling_price": selling_price,
                "batch_value": quantity * purchase_price
            })
        
        # Convert to list
        stocks_data = list(product_valuation.values())
        
        # Calculate totals
        total_purchase_value = sum(item["total_purchase_value"] for item in stocks_data)
        total_selling_value = sum(item["total_selling_value"] for item in stocks_data)
        total_quantity = sum(item["total_quantity"] for item in stocks_data)
        potential_profit = total_selling_value - total_purchase_value
        profit_margin = (potential_profit / total_purchase_value * 100) if total_purchase_value > 0 else 0
        
        return Response({
            "status": "success",
            "company": company.name,
            "valuation_date": str(today),
            "summary": {
                "total_products": len(stocks_data),
                "total_batches": batches.count(),
                "total_quantity": total_quantity,
                "total_purchase_value": round(total_purchase_value, 2),
                "total_selling_value": round(total_selling_value, 2),
                "potential_profit": round(potential_profit, 2),
                "profit_margin": round(profit_margin, 2),
            },
            "stocks": stocks_data
        })
    
class OutOfStockAPIView(APIView):
    """
    API: GET /api/stocks/out-of-stock/
    Returns products that are out of stock (no active, non-expired inventory)
    """
    renderer_classes = [JSONRenderer]

    def get(self, request):
        # Get user's company
        try:
            profile = UserProfile.objects.select_related("company").get(user=request.user)
            company = profile.company
        except UserProfile.DoesNotExist:
            return Response({"error": "Authentication required"}, status=401)
        
        today = date.today()
        
        # Get all products for this company
        all_products = Product.objects.filter(company=company)
        
        out_of_stock_products = []
        
        for product in all_products:
            # Check for active, non-expired stock
            active_stock = ProductBatch.objects.filter(
                company=company,
                product=product,
                quantity__gt=0,
                is_active=True,
                expiry_date__gte=today
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Check for any stock at all (even expired)
            any_stock = ProductBatch.objects.filter(
                company=company,
                product=product,
                quantity__gt=0
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Product is out of stock if no active, non-expired stock
            if active_stock == 0:
                # Get all batches for this product
                batches = ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    quantity__gt=0
                ).order_by('-created_at')
                
                batch_details = []
                total_expired_qty = 0
                
                for batch in batches:
                    is_expired = batch.expiry_date and batch.expiry_date < today
                    if is_expired:
                        total_expired_qty += batch.quantity
                    
                    batch_details.append({
                        "batch_number": batch.batch_number or "NO-BATCH",
                        "quantity": batch.quantity,
                        "expiry_date": batch.expiry_date,
                        "expiry_date_formatted": batch.expiry_date.strftime("%d %b %Y") if batch.expiry_date else "N/A",
                        "is_expired": is_expired,
                        "days_to_expiry": (batch.expiry_date - today).days if batch.expiry_date else None
                    })
                
                out_of_stock_products.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "category": product.category.name if product.category else "Uncategorized",
                    "purchase_price": float(product.purchase_price),
                    "selling_price": float(product.selling_price),
                    "status": "OUT_OF_STOCK",
                    "status_class": "text-danger",
                    "has_expired_stock": total_expired_qty > 0,
                    "total_expired_quantity": total_expired_qty,
                    "last_stock_date": batches[0].created_at.date() if batches.exists() else None,
                    "last_stock_date_formatted": batches[0].created_at.strftime("%d %b %Y") if batches.exists() else "N/A",
                    "batches": batch_details
                })
        
        return Response({
            "status": "success",
            "company": company.name,
            "report_date": str(today),
            "report_date_formatted": today.strftime("%d %b %Y"),
            "summary": {
                "total_products": all_products.count(),
                "out_of_stock_products": len(out_of_stock_products),
                "in_stock_products": all_products.count() - len(out_of_stock_products),
                "products": out_of_stock_products
            },
            "count": len(out_of_stock_products),
            "items": out_of_stock_products  # For backward compatibility
        })




class StockMovementReportAPIView(APIView):
    """
    Comprehensive stock movement report with all filters
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        # Get query parameters
        transaction_type = request.GET.get('transaction_type')  # IN, OUT, ADJUSTMENT
        source_type = request.GET.get('source')  # PURCHASE, SALE, RETURN, DAMAGE, ADJUSTMENT
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        product_id = request.GET.get('product_id')
        user_id = request.GET.get('user_id')
        reference_number = request.GET.get('reference_number')
        batch_number = request.GET.get('batch_number')
        
        # Build queryset
        queryset = StockTransaction.objects.filter(
            company=company
        ).select_related(
            'product', 'batch', 'created_by'
        ).order_by('-created_at')
        
        # Apply filters
        if transaction_type:
            queryset = queryset.filter(transaction_type=transaction_type)
        
        if source_type:
            queryset = queryset.filter(source=source_type)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        if user_id:
            queryset = queryset.filter(created_by_id=user_id)
        
        if reference_number:
            queryset = queryset.filter(reference_number__icontains=reference_number)
        
        if batch_number:
            queryset = queryset.filter(batch__batch_number__icontains=batch_number)
        
        # Prepare response data
        data = []
        for transaction in queryset:
            data.append({
                'id': transaction.id,
                'date': transaction.created_at,
                'product_name': transaction.product.name if transaction.product else 'N/A',
                'batch_number': transaction.batch.batch_number if transaction.batch else 'N/A',
                'transaction_type': transaction.transaction_type,
                'source': transaction.source,
                'quantity': transaction.quantity,
                'reference_number': transaction.reference_number or 'N/A',
                'created_by': transaction.created_by.username if transaction.created_by else 'System',
                'note': transaction.note or '',
            })
        
        return Response({
            'status': 'success',
            'count': len(data),
            'filters': {
                'transaction_type': transaction_type,
                'source': source_type,
                'start_date': start_date,
                'end_date': end_date,
                'product_id': product_id,
                'user_id': user_id,
                'reference_number': reference_number,
                'batch_number': batch_number,
            },
            'results': data
        })


class StockInReportAPIView(APIView):
    """
    Stock In report (Purchases, Returns)
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        source_type = request.GET.get('source_type')  # PURCHASE, RETURN, etc.
        
        queryset = StockTransaction.objects.filter(
            company=company,
            transaction_type='IN'
        ).select_related('product', 'batch', 'created_by')
        
        if source_type:
            queryset = queryset.filter(source=source_type)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Group by source type for summary
        summary = queryset.values('source').annotate(
            total_quantity=Sum('quantity'),
            transaction_count=Count('id')
        )
        
        # Detailed transactions
        transactions = []
        for txn in queryset.order_by('-created_at'):
            transactions.append({
                'id': txn.id,
                'date': txn.created_at.date(),
                'product': txn.product.name if txn.product else 'N/A',
                'batch': txn.batch.batch_number if txn.batch else 'N/A',
                'source': txn.source,
                'quantity': txn.quantity,
                'reference': txn.reference_number or 'N/A',
                'user': txn.created_by.username if txn.created_by else 'System',
                'note': txn.note or '',
            })
        
        return Response({
            'status': 'success',
            'summary': list(summary),
            'transactions': transactions,
            'total_transactions': queryset.count(),
            'total_quantity': queryset.aggregate(Sum('quantity'))['quantity__sum'] or 0
        })


class StockOutReportAPIView(APIView):
    """
    Stock Out report (Sales, Damages, Expiry)
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        source_type = request.GET.get('source_type')  # SALE, DAMAGE, EXPIRY
        
        queryset = StockTransaction.objects.filter(
            company=company,
            transaction_type='OUT'
        ).select_related('product', 'batch', 'created_by')
        
        if source_type:
            queryset = queryset.filter(source=source_type)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Summary by source
        summary = queryset.values('source').annotate(
            total_quantity=Sum('quantity'),
            transaction_count=Count('id')
        )
        
        # Detailed transactions
        transactions = []
        for txn in queryset.order_by('-created_at'):
            transactions.append({
                'id': txn.id,
                'date': txn.created_at.date(),
                'product': txn.product.name if txn.product else 'N/A',
                'batch': txn.batch.batch_number if txn.batch else 'N/A',
                'source': txn.source,
                'quantity': txn.quantity,
                'reference': txn.reference_number or 'N/A',
                'user': txn.created_by.username if txn.created_by else 'System',
                'note': txn.note or '',
            })
        
        return Response({
            'status': 'success',
            'summary': list(summary),
            'transactions': transactions,
            'total_transactions': queryset.count(),
            'total_quantity': queryset.aggregate(Sum('quantity'))['quantity__sum'] or 0
        })


class AdjustmentHistoryAPIView(APIView):
    """
    Adjustment history report
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        product_id = request.GET.get('product_id')
        
        queryset = StockTransaction.objects.filter(
            company=company,
            source='MANUAL'
        ).select_related('product', 'batch', 'created_by')
        
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Summary by adjustment type
        summary = queryset.values('transaction_type').annotate(
            total_quantity=Sum('quantity'),
            transaction_count=Count('id')
        )
        
        # Detailed adjustments
        adjustments = []
        for txn in queryset.order_by('-created_at'):
            adjustments.append({
                'id': txn.id,
                'date': txn.created_at.date(),
                'product': txn.product.name if txn.product else 'N/A',
                'batch': txn.batch.batch_number if txn.batch else 'N/A',
                'type': txn.transaction_type,
                'quantity': txn.quantity,
                'reference': txn.reference_number or 'N/A',
                'user': txn.created_by.username if txn.created_by else 'System',
                'note': txn.note or '',
            })
        
        return Response({
            'status': 'success',
            'summary': list(summary),
            'adjustments': adjustments,
            'total_adjustments': queryset.count()
        })


class DateWiseMovementAPIView(APIView):
    """
    Date-wise stock movement summary
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        group_by = request.GET.get('group_by', 'day')  # day, month
        
        queryset = StockTransaction.objects.filter(
            company=company
        )
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        if group_by == 'month':
            # Group by month
            data = queryset.annotate(
                period=TruncMonth('created_at')
            ).values('period').annotate(
                stock_in=Sum('quantity', filter=Q(transaction_type='IN')),
                stock_out=Sum('quantity', filter=Q(transaction_type='OUT')),
                net_movement=Sum(
                    Case(
                        When(transaction_type='IN', then=F('quantity')),
                        When(transaction_type='OUT', then=-F('quantity')),
                        default=Value(0),
                        output_field=models.IntegerField()
                    )
                ),
                transaction_count=Count('id')
            ).order_by('-period')
        else:
            # Group by day (default)
            data = queryset.annotate(
                period=TruncDate('created_at')
            ).values('period').annotate(
                stock_in=Sum('quantity', filter=Q(transaction_type='IN')),
                stock_out=Sum('quantity', filter=Q(transaction_type='OUT')),
                net_movement=Sum(
                    Case(
                        When(transaction_type='IN', then=F('quantity')),
                        When(transaction_type='OUT', then=-F('quantity')),
                        default=Value(0),
                        output_field=models.IntegerField()
                    )
                ),
                transaction_count=Count('id')
            ).order_by('-period')
        
        return Response({
            'status': 'success',
            'group_by': group_by,
            'results': list(data),
            'total_days': len(data)
        })


class UserActivityAPIView(APIView):
    """
    User-wise stock activity report
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        user_id = request.GET.get('user_id')
        
        queryset = StockTransaction.objects.filter(
            company=company
        ).select_related('created_by')
        
        if user_id:
            queryset = queryset.filter(created_by_id=user_id)
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Summary by user
        user_summary = queryset.values(
            'created_by__id', 
            'created_by__username'
        ).annotate(
            total_transactions=Count('id'),
            total_quantity_moved=Sum('quantity'),
            stock_in=Sum('quantity', filter=Q(transaction_type='IN')),
            stock_out=Sum('quantity', filter=Q(transaction_type='OUT'))
        ).order_by('-total_transactions')
        
        # Get all users for dropdown
        users = User.objects.filter(
            stocktransaction__company=company
        ).distinct().values('id', 'username')
        
        return Response({
            'status': 'success',
            'user_summary': list(user_summary),
            'available_users': list(users),
            'total_users': len(user_summary)
        })


class TransactionReferenceAPIView(APIView):
    """
    Transaction reference reports (PO, GRN, Invoice)
    """
    def get(self, request):
        profile = UserProfile.objects.get(user=request.user)
        company = profile.company
        
        reference_type = request.GET.get('reference_type')  # PO, SO, GRN, etc.
        reference_number = request.GET.get('reference_number')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        queryset = StockTransaction.objects.filter(
            company=company
        ).select_related('product', 'batch', 'created_by')
        
        if reference_type:
            # Filter by reference number prefix
            queryset = queryset.filter(
                reference_number__startswith=reference_type
            )
        
        if reference_number:
            queryset = queryset.filter(
                reference_number__icontains=reference_number
            )
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Group by reference number
        reference_summary = queryset.values('reference_number').annotate(
            total_quantity=Sum('quantity'),
            transaction_count=Count('id'),
            stock_in=Sum('quantity', filter=Q(transaction_type='IN')),
            stock_out=Sum('quantity', filter=Q(transaction_type='OUT'))
        ).order_by('-transaction_count')
        
        # Detailed transactions by reference
        transactions_by_reference = {}
        for ref in reference_summary:
            ref_num = ref['reference_number']
            if ref_num:
                ref_transactions = queryset.filter(
                    reference_number=ref_num
                ).order_by('-created_at')
                
                transactions_by_reference[ref_num] = [
                    {
                        'id': txn.id,
                        'date': txn.created_at.date(),
                        'product': txn.product.name if txn.product else 'N/A',
                        'type': txn.transaction_type,
                        'source': txn.source,
                        'quantity': txn.quantity,
                        'user': txn.created_by.username if txn.created_by else 'System',
                    }
                    for txn in ref_transactions[:10]  # Limit to 10 per reference
                ]
        
        return Response({
            'status': 'success',
            'reference_summary': list(reference_summary),
            'transactions_by_reference': transactions_by_reference,
            'total_unique_references': len(reference_summary)
        })



@login_required
def abc_inventory_classification(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    products = Product.objects.filter(company=company)

    product_list = []

    # Calculate inventory value
    for p in products:
        value = p.stock_quantity * p.purchase_price
        product_list.append((p, value))

    # Sort by highest inventory value
    product_list.sort(key=lambda x: x[1], reverse=True)

    total_value = sum([item[1] for item in product_list])

    running_value = 0
    sorted_products = []

    #  NEW counters
    a_count = b_count = c_count = 0
    a_value = b_value = c_value = 0

    for product, value in product_list:

        running_value += value
        percent = (running_value / total_value) * 100 if total_value else 0

        # ABC classification
        if percent <= 70:
            product.abc_class = "A"
            a_count += 1
            a_value += value
        elif percent <= 90:
            product.abc_class = "B"
            b_count += 1
            b_value += value
        else:
            product.abc_class = "C"
            c_count += 1
            c_value += value

        product.save(update_fields=["abc_class"])
        sorted_products.append(product)

    total_products = len(sorted_products)

    # SAFE PERCENT FUNCTION
    def get_percent(count):
        return round((count / total_products) * 100, 1) if total_products else 0

    def get_value_percent(val):
        return round((val / total_value) * 100, 1) if total_value else 0

    # Pagination
    paginator = Paginator(sorted_products, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "inventory/abc_classification.html",
        {
            "products": page_obj,
            "company": company,

            #  DYNAMIC COUNTS
            "a_percent": get_percent(a_count),
            "b_percent": get_percent(b_count),
            "c_percent": get_percent(c_count),

            #  DYNAMIC VALUE CONTRIBUTION
            "a_value_percent": get_value_percent(a_value),
            "b_value_percent": get_value_percent(b_value),
            "c_value_percent": get_value_percent(c_value),
        }
    )



def reports(request):

    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    search = request.GET.get("search")

    reports = SalesOrder.objects.all()

    # Date Filter
    if from_date and to_date:
        reports = reports.filter(date__range=[from_date, to_date])

    # Search Filter
    if search:
        reports = reports.filter(
            Q(order_number__icontains=search)
        )

    context = {
        "reports": reports
    }

    return render(request, "report.html", context)




@require_POST
def bulk_delete_products(request):
    ids = request.POST.getlist('product_ids')

    if ids:
        Product.objects.filter(id__in=ids).delete()

    messages.success(request, "Selected products deleted successfully.")
    return redirect('product_list')

@login_required
def export_product_pdf(request, pk):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    product = get_object_or_404(Product, id=pk, company=company)

    batches = ProductBatch.objects.filter(
        product=product,
        company=company
    )

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{product.name}_stock.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph(f"{product.name} - Stock Report", styles["Title"]))
    elements.append(Spacer(1, 10))

    # Product Info
    elements.append(Paragraph(f"Company: {company.name}", styles["Normal"]))
    elements.append(Paragraph(f"SKU: {product.sku}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    # Table Data
    data = [["Batch", "Quantity", "Expiry Date"]]

    for b in batches:
        data.append([
            b.batch_number or "NO-BATCH",
            str(b.quantity),
            b.expiry_date.strftime("%d-%m-%Y") if b.expiry_date else "-"
        ])

    table = Table(data, colWidths=[150, 100, 150])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.transparent]),
    ]))

    elements.append(table)

    doc.build(elements)

    return response

def get_batch_stock_queryset(request, company):
    status = request.GET.get("status")
    query = request.GET.get("q", "").strip()

    today = date.today()
    near_limit = today + timedelta(days=30)

    batches = ProductBatch.objects.filter(
        company=company,
        quantity__gt=0
    ).select_related("product")

    # STATUS FILTER
    if status == "expired":
        batches = batches.filter(expiry_date__lt=today)

    elif status == "near_expiry":
        batches = batches.filter(
            expiry_date__gte=today,
            expiry_date__lte=near_limit
        )

    else:
        batches = batches.filter(expiry_date__gte=today)

    # SEARCH
    if query:
        batches = batches.filter(
            Q(batch_number__icontains=query) |
            Q(product__name__icontains=query)
        )

    return batches.order_by("expiry_date")


