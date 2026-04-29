from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from company.models import Transaction
from accounts.models import UserProfile
from django.core.paginator import Paginator
from django.shortcuts import  get_object_or_404
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from datetime import date, timedelta
from reportlab.pdfgen import canvas
from company.models import Company, Staff
from inventory.models import StockTransaction, Product, ProductBatch, SalesOrder 
import csv
from django.db import IntegrityError
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from django.db.models import Sum
from django.db.models.functions import TruncDate
from datetime import timedelta, date
import json
from datetime import datetime
from django.db.models import Sum
from django.db.models import Q 
from django.db.models.functions import Coalesce
from inventory.models import InventoryAlert
import random
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

# COMPANY OWNER LOGIN

def company_login(request):
    if request.user.is_authenticated:
        # If already logged in, redirect safely to dashboard
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.role == "COMPANY_OWNER":
            return redirect("company_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            profile = UserProfile.objects.filter(user=user).first()

            if profile and profile.role == "COMPANY_OWNER":
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect("company_dashboard")
            else:
                messages.error(request, "Access denied: This portal is for company owners only.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "company/company_login.html")





@login_required
def company_dashboard(request):
    #  Safe profile fetch
    profile = UserProfile.objects.filter(user=request.user).first()

    #  Role validation (CRITICAL FIX)
    if not profile or profile.role != "COMPANY_OWNER":
        messages.error(request, "Access denied. Please login as Company Owner.")
        return redirect("company_login")
    
    company = profile.company

    # Welcome Banner Efficiency logic & count
    total_orders = SalesOrder.objects.filter(company=company).count()
    delivered_orders = SalesOrder.objects.filter(company=company, status="DELIVERED").count()

    efficiency = 0
    if total_orders > 0:
        efficiency = round((delivered_orders/total_orders)*100)
    # 26-2-26 - Added pending shipments count to dashboard context
    pending_shipments = SalesOrder.objects.filter(
        company=company
    ).filter(
        Q(status__iexact='pending') |
        Q(status__iexact='processing')
    ).count()

    # 26-2-26 Count Out of Stock Products
    products = Product.objects.filter(company=company).annotate(
        total_stock=Coalesce(Sum('productbatch__quantity'), 0)
    )

    out_of_stock_count = products.filter(total_stock=0).count()

    # Recent 5 Sales Orders with items + products (optimized)
    transactions = (
        SalesOrder.objects
        .filter(company=company)
        .select_related("company")
        .prefetch_related("items__product")
        .order_by("-created_at")[:5]
    )

    # Attach product names + total quantity per order
    for order in transactions:
        order.product_names = ", ".join(
            [item.product.name for item in order.items.all()]
        )
        order.total_quantity = sum(
            item.quantity for item in order.items.all()
        )

    today = date.today()
    near_expiry_limit = today + timedelta(days=30)

    #  Product counts
    total_products = Product.objects.filter(company=company).count()

    low_stock_products = Product.objects.filter(
            company=company,
            stock_quantity__gt=0,
            stock_quantity__lte=5
        ).count()

    # 26-2-26
    # Total Revenue (only DELIVERED orders)
    total_revenue = SalesOrder.objects.filter(
        company=company,
        status="DELIVERED"
    ).aggregate(total=Sum("total_amount"))["total"] or 0

    #  Batch health - Expired batches list
    expired_batches_list = ProductBatch.objects.filter(
        company=company,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=date.today(),
        quantity__gt=0
    ).select_related('product').order_by('expiry_date')

    expired_batches = expired_batches_list.count()

    #  Current/Active batches list
    current_batches_list = ProductBatch.objects.filter(
        company=company,
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__gte=date.today()
    ).select_related('product').order_by('expiry_date')

    near_expiry_batches = current_batches_list.filter(
        expiry_date__range=(today, near_expiry_limit),
        quantity__gt=0
    ).count()



    #  UNREAD INVENTORY ALERTS (NEW)
    unread_alerts_count = InventoryAlert.objects.filter(
        company=company,
        is_read=False
    ).count()
    # Sales Trend - Last 7 Days (DELIVERED Orders)
    last_7_days = today - timedelta(days=6)

    sales_qs = (
        SalesOrder.objects
        .filter(
            company=company,
            status="DELIVERED",
            created_at__date__gte=last_7_days
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total_amount"))
        .order_by("day")
    )

    # Convert queryset to dictionary
    sales_dict = {item["day"]: item["total"] for item in sales_qs}

    # Ensure all 7 days appear (even if 0 sales)
    sales_trend = []
    for i in range(7):
        day = last_7_days + timedelta(days=i)
        sales_trend.append({
            "day": day.strftime("%d %b"),
            "total": float(sales_dict.get(day, 0))
        })

    context = {
        "total_products": total_products,
        "low_stock_products": low_stock_products,
        "expired_batches": expired_batches,
        "near_expiry_batches": near_expiry_batches,
        "unread_alerts_count": unread_alerts_count,  # NEW
        "total_revenue": total_revenue, # 26-2-26
        "pending_shipments": pending_shipments, # 26-2-26
        "company": company,
        "transactions": transactions,
        "out_of_stock_count": out_of_stock_count, # 26-2-26
        "sales_trend": json.dumps(sales_trend),
        "efficiency": efficiency,

    }

    return render(
        request,
        "company/company_dashboard.html",
        context
    )


# OPERATIONS & PAGES

from .models import NewEntry
@login_required
def new_entry(request):

    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    if request.method == "POST":
        entry_name = request.POST.get("entry_name")
        description = request.POST.get("description")

        if not entry_name:
            return redirect("new_entry")

        # Save entry
        NewEntry.objects.create(
            company=company,
            entry_name=entry_name,
            description=description
        )

        # Redirect with success flag
        return redirect("/company/new-entry/?success=1")

    entries = NewEntry.objects.filter(company=company).order_by("-created_at")

    context = {
        "company": company,
        "entries": entries
    }

    return render(request, "company/new_entry.html", context)

@login_required
def delete_entry(request, entry_id):

    entry = NewEntry.objects.get(id=entry_id)

    entry.delete()

    return redirect("new_entry")

@login_required
def reports_page(request):
    return render(request, "company/reports.html")

@login_required
def add_stock(request):
    return render(request, "company/add_stock.html")

@login_required
def dispatcher(request):
    if request.method == "POST":
        order_number = request.POST.get('order_number')
        dispatch_date = request.POST.get('dispatch_date')

        if not dispatch_date:
            return render(request, 'company/dispatch.html', {
                'error': 'Dispatch Date is required.'
            })

        
        messages.success(request, "Order dispatched successfully.")
        return redirect('dispatch')

   
    return render(request, 'company/dispatch.html')

@login_required
def add_staff(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    if request.method == "POST":
        name = request.POST.get("staff_name")
        email = request.POST.get("email")

        # Create Staff
        Staff.objects.create(
            company=company,
            name=name,
            email=email
        )

        messages.success(request, "Staff member added successfully.")

        return redirect("staff_list")  # reload page to show message

    return render(request, "company/add_staff.html")

@login_required
def export_data(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    # When user clicks Export Now
    if request.method == "POST":
        return redirect("export_data_download")

    return render(request, "company/export.html", {"company": company})




@login_required
def export_data_download(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="company_data.csv"'

    writer = csv.writer(response)
    writer.writerow(["Product Name", "Stock Quantity"])

    products = Product.objects.filter(company=company)

    for p in products:
        writer.writerow([p.name, p.stock_quantity])

    return response

@login_required
def transactions_list(request):
    profile = UserProfile.objects.select_related("company").filter(user=request.user).first()

    if not profile or profile.role != "COMPANY_OWNER":
        return redirect("company_login")

    # Get all transactions
    transaction_list = Transaction.objects.filter(company=profile.company).order_by("-created_at")
    
    # Set up pagination (e.g., 10 transactions per page)
    paginator = Paginator(transaction_list, 10) 
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)

    return render(request, "company/transactions_list.html", {"transactions": transactions})


# COMPANY OWNER LOGOUT

def company_logout(request):
    user_role = None
    is_superuser = False

    if request.user.is_authenticated:
        is_superuser = request.user.is_superuser  #  store BEFORE logout
        
        try:
            profile = UserProfile.objects.get(user=request.user)
            user_role = profile.role
        except UserProfile.DoesNotExist:
            pass

    logout(request)

    messages.success(request, "You have been logged out successfully.")

    #  Now use stored values
    if user_role == 'COMPANY_OWNER':
        return redirect('company_login')
    elif is_superuser:
        return redirect('admin_login')

    return redirect('company_login')


# SETTINGS

@login_required
def company_settings(request):
    profile = UserProfile.objects.select_related("company").get(user=request.user)

    if profile.role != "COMPANY_OWNER":
        return redirect("company_login")

    company = profile.company

    if request.method == "POST":
        name = request.POST.get("company_name", "").strip()
        email = request.POST.get("company_email", "").strip()
        new_password = request.POST.get("new_password")  

        if not name:
            messages.error(request, "Company name cannot be empty or only spaces")
            return redirect("company_settings")

        # Email
        EMAIL_REGEX = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not email or not re.match(EMAIL_REGEX, email):
            messages.error(request, "Enter a valid email")
            return redirect("company_settings")

        # Password (REQUIRED FIX)
        if not new_password:
            messages.error(request, "Password is required")
            return redirect("company_settings")

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters")
            return redirect("company_settings")


        company.name = name
        company.email = email

        try:
            company.save()
        except IntegrityError:
            messages.error(request, "Email already exists")
            return redirect("company_settings")


        request.user.set_password(new_password)
        request.user.save()

        # Keep user logged in after password change
        update_session_auth_hash(request, request.user)


        messages.success(request, "Settings updated successfully")
        return redirect("company_settings")

    return render(request, "company/company_settings.html", {
        "company": company
    })



@login_required
def export_stock_movement_pdf(request, pk=None):
    company = Company.objects.get(owner=request.user)

    # Base queryset
    transactions = StockTransaction.objects.filter(
        product__company=company
    )

    product = None

    # Filter by product (optional)
    if pk:
        product = get_object_or_404(Product, id=pk, company=company)
        transactions = transactions.filter(product=product)

    # Apply filters
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")
    flow_type = request.GET.get("flow_type")

    if from_date:
        transactions = transactions.filter(created_at__date__gte=from_date)

    if to_date:
        transactions = transactions.filter(created_at__date__lte=to_date)

    if flow_type:
        transactions = transactions.filter(transaction_type=flow_type)

    transactions = transactions.order_by('-created_at')

    # Response
    response = HttpResponse(content_type='application/pdf')

    filename = f"{company.name}_stock_report.pdf"
    if product:
        filename = f"{product.name}_stock_report.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # PDF setup
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

    # Custom styles
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.white,
        alignment=1,
        spaceAfter=6
    )

    table_text_style = ParagraphStyle(
        name="TableText",
        fontSize=9,
        leading=11,
    )

    # Header title
    title = f"{company.name} - Stock Movement Report"
    if product:
        title = f"{product.name} - Stock Movement Report"

    header_table = Table([[Paragraph(title, header_style)]], colWidths=[520])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#4071db")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 8))

    # Generated date
    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 15))

    # Table data
    data = [["Date", "Product", "Type", "Quantity"]]

    for t in transactions:
        data.append([
            t.created_at.strftime("%d-%m-%Y"),
            Paragraph(t.product.name, table_text_style),  #  wrapped text
            Paragraph(t.transaction_type, table_text_style),
            Paragraph(str(t.quantity), table_text_style),
        ])

    # Table with better column widths
    table = Table(data, colWidths=[100, 240, 90, 70])

    table.setStyle(TableStyle([
        # Header styling
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        # Body styling
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (3, 1), (3, -1), "CENTER"),

        # Alternating rows
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f1f5f9"), colors.white]),

        # Grid
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),

        # Padding
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),

        # Wrap product column
        ('WORDWRAP', (1, 1), (1, -1), 'CJK'),
    ]))

    elements.append(table)

    doc.build(elements)
    return response

@login_required
def staff_list(request):
    profile = UserProfile.objects.get(user=request.user)
    company = profile.company

    staff_members = Staff.objects.filter(company=company)
    return render(request, "company/staff_list.html", {
        "staff_members": staff_members
    })

def forgot_password(request):

    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()

        if profile and profile.role == "COMPANY_OWNER":
            return redirect("company_dashboard")

    if request.method == "POST":

        email = request.POST.get("email")

        profile = Company.objects.filter(email=email).first()

        if not profile:
            messages.error(request, "No account found with this email")
            return redirect("forgot_password")

        otp = random.randint(100000, 999999)

        request.session['reset_otp'] = str(otp)
        request.session['reset_user'] = profile.id
        request.session["otp_resend_count"] = 0

        send_mail(
            "Password Reset OTP",
            f"Your OTP for password reset is {otp}",
            settings.EMAIL_HOST_USER,
            [email],
            fail_silently=False
        )

        return redirect("verify_otp")

    return render(request, "company/forgot_password.html")


def verify_otp(request):

    if request.method == "POST":

        entered_otp = request.POST.get("otp")
        session_otp = request.session.get("reset_otp")

        if str(entered_otp) == str(session_otp):

            return redirect("reset_password")

        else:
            messages.error(request,"Invalid OTP")
            return redirect("forgot_password")

    return render(request,"company/verify_otp.html")



def resend_otp(request):

    resend_count = request.session.get("otp_resend_count",0)

    if resend_count >=3:
        return JsonResponse({"error":"limit reached"})

    user_id = request.session.get("reset_user")

    user = Company.objects.get(id=user_id)

    otp = random.randint(100000,999999)

    request.session["reset_otp"] = str(otp)
    request.session["otp_resend_count"] = resend_count + 1

    send_mail(
        "Password Reset OTP",
        f"Your new OTP is {otp}",
        settings.EMAIL_HOST_USER,
        [user.email],
        fail_silently=False
    )

    return JsonResponse({"status":"sent"})


def reset_password(request):

    user_id = request.session.get("reset_user")

    if not user_id:
        messages.error(request, "Session expired. Please try again.")
        return redirect("forgot_password")

    if request.method == "POST":

        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return redirect("reset_password")

        company = Company.objects.get(id=user_id)
        user = company.owner

        user.set_password(password)
        user.save()

        request.session.pop("reset_user", None)
        request.session.pop("reset_otp", None)

        return redirect("company_login")

    return render(request, "company/reset_password.html")