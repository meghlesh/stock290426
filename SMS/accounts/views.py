from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import logout
import re
from company.models import Company
from .models import UserProfile
email_regex = r'^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

def delete_company(request, id):
    if request.method == "POST":
        company = get_object_or_404(Company, id=id)
        company.delete()
        messages.error(request, "Company deleted successfully.")
    return redirect('admin_dashboard')

def edit_company(request, id):
    if not request.user.is_superuser:
        return redirect("admin_login")

    company = get_object_or_404(Company, id=id)

    if request.method == "POST":
        # 16-4-26: added default "" to prevent None error + safe strip
        name = request.POST.get("company_name", "").strip()
        email = request.POST.get("company_email", "").strip()

        
        # 16-4-26: START - NAME VALIDATION (FIX FOR 500 ERROR)
        
        if not name:
            messages.error(request, "Company name cannot be empty.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        if len(name) > 50:  
            messages.error(request, "Company name cannot exceed 50 characters.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})
        
        # 16-4-26: END - NAME VALIDATION
        

        #  Email validation (existing logic kept)
        pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            messages.error(request, "Invalid email format.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        #  Duplicate name check
        if Company.objects.filter(name__iexact=name).exclude(id=company.id).exists():
            messages.error(request, "Company name already exists.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        # 16-4-26: OPTIONAL BUT IMPORTANT - email uniqueness check
        if Company.objects.filter(email__iexact=email).exclude(id=company.id).exists():
            messages.error(request, "Company email already exists.")
            company.name = name
            company.email = email
            return render(request, "accounts/edit_company.html", {"company": company})

        #  Safe save (no more DB crash)
        company.name = name
        company.email = email
        company.save()

        messages.success(request, "Company updated successfully.")
        return redirect("admin_dashboard")

    return render(request, "accounts/edit_company.html", {"company": company})




def company_list(request):
    if not request.user.is_superuser:
        return redirect("admin_login")

    companies = Company.objects.select_related("owner")

    return render(
        request,
        "accounts/company_list.html",
        {"companies": companies}
    )





# ADMIN LOGIN
def admin_login(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_superuser:
                login(request, user)

                #  SUCCESS MESSAGE (THIS WAS MISSING)
                messages.success(request, "Login successful")

                return redirect("admin_dashboard")
            else:
                messages.error(request, "You are not authorized to access admin panel.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/admin_login.html")

# ADMIN DASHBOARD (COMPANY MANAGEMENT ONLY)

@login_required
def admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect("admin_login")

    companies = Company.objects.select_related("owner")
    total_companies = Company.objects.count()
    total_users = User.objects.count()

    # CREATE COMPANY + OWNER
    if request.method == "POST":
        # Get inputs and strip whitespace
        company_name = request.POST.get("company_name", "").strip()
        company_email = request.POST.get("company_email", "").strip()
        owner_username = request.POST.get("owner_username", "").strip()
        owner_password = request.POST.get("owner_password", "").strip()

        # VALIDATIONS
        if not company_name:
            messages.error(request, "Company Name cannot be empty or whitespace.")
            return redirect("admin_dashboard")
        
        
        
        if len(company_name) > 50:
            messages.error(request, "Company Name should not exceed 50 characters.")
            return redirect("admin_dashboard")
        


        if not company_email:
            messages.error(request, "Company Email cannot be empty.")
            return redirect("admin_dashboard")
        
        if " " in company_email:
            messages.error(request, "Please enter a valid email address.")
            return redirect("admin_dashboard")
        
        if not re.match(email_regex, company_email):
            messages.error(request, "Email must start with a letter/number and follow a valid format.")
            return redirect("admin_dashboard")
        
        try:
            validate_email(company_email)
        except ValidationError:
            messages.error(request, "Please enter a valid email address.")
            return redirect("admin_dashboard")
        
        if Company.objects.filter(name__iexact=company_name).exists():
            messages.error(request, "Company with this name already exists.")
            return redirect("admin_dashboard")

        if Company.objects.filter(email__iexact=company_email).exists():
            messages.error(request, "Company with this email already exists.")
            return redirect("admin_dashboard")

        if not owner_username:
            messages.error(request, "Owner Username cannot be empty.")
            return redirect("admin_dashboard")
        
        if len(owner_username) > 30:
            messages.error(request, "Owner Username should not exceed 30 characters.")
            return redirect("admin_dashboard")
        if " " in owner_username:
            messages.error(request, "Owner Username cannot contain spaces.")
            return redirect("admin_dashboard")      

        if not owner_password:
            messages.error(request, "Owner Password cannot be empty.")
            return redirect("admin_dashboard")
        
        if len(owner_password) < 8 or len(owner_password) > 16:
            messages.error(request, "Owner Password must be between 8 and 16 characters.")
            return redirect("admin_dashboard")
        if " " in owner_password:
            messages.error(request, "Owner Password cannot contain spaces.")
            return redirect("admin_dashboard")      

        # Optional: check if username already exists
        if User.objects.filter(username=owner_username).exists():
            messages.error(request, f"Username '{owner_username}' already exists.")
            return redirect("admin_dashboard")

        # Create owner
        owner = User.objects.create_user(
            username=owner_username,
            password=owner_password
        )

        # Create company
        company = Company.objects.create(
            name=company_name,
            email=company_email,
            owner=owner
        )

        # Create user profile
        UserProfile.objects.create(
            user=owner,
            role="COMPANY_OWNER",
            company=company
        )

        messages.success(request, f"Company '{company_name}' created successfully.")
        return redirect("admin_dashboard")

    return render(
        request,
        "accounts/admin_dashboard.html",
        {
            "companies": companies,
            "total_companies": total_companies,
            "total_users": total_users,
        }
        
    )


@login_required
def notifications(request):
    return render(request, "accounts/notifications.html")


@login_required
def admin_logout(request):
    logout(request)
    return redirect("admin_login")