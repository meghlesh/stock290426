import re
from django import forms
from .models import Vendor


class VendorForm(forms.ModelForm):

    class Meta:
        model = Vendor
        fields = "__all__"

    
    # GST NUMBER VALIDATION
    
    def clean_gst_number(self):
        gst = self.cleaned_data.get("gst_number", "").upper()

        if not gst:
            raise forms.ValidationError("GST number is required.")

        gst_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'

        if not re.match(gst_regex, gst):
            raise forms.ValidationError(
                "Invalid GST format. (e.g., 22AAAAA0000A1Z5)"
            )

        # Prevent duplicate GST
        if Vendor.objects.filter(gst_number=gst).exists():
            raise forms.ValidationError("Vendor with this GST already exists.")

        return gst


    
    # PRIMARY CONTACT – FIRST NAME
    
    def clean_primary_contact_first_name(self):
        name = self.cleaned_data.get("primary_contact_first_name", "")

        if not name:
            raise forms.ValidationError("First name is required.")

        if len(name) > 20:
            raise forms.ValidationError("First name cannot exceed 20 characters.")

        if not re.match(r'^[A-Za-z]+$', name):
            raise forms.ValidationError(
                "First name should contain only alphabetic characters."
            )

        return name


    
    # PRIMARY CONTACT – LAST NAME
    
    def clean_primary_contact_last_name(self):
        name = self.cleaned_data.get("primary_contact_last_name", "")

        if not name:
            raise forms.ValidationError("Last name is required.")

        if len(name) > 20:
            raise forms.ValidationError("Last name cannot exceed 20 characters.")

        if not re.match(r'^[A-Za-z]+$', name):
            raise forms.ValidationError(
                "Last name should contain only alphabetic characters."
            )

        return name


    
    # VENDOR NAME
    
    def clean_company_name(self):
        name = self.cleaned_data.get("company_name", "")

        if not name:
            raise forms.ValidationError("Vendor name is required.")

        if len(name) > 50:
            raise forms.ValidationError("Vendor name cannot exceed 50 characters.")

        if not re.match(r'^[A-Za-z][A-Za-z\s&.\-]*$', name):
            raise forms.ValidationError(
                "Vendor name must start with a letter and contain only alphabets, spaces, &, . or -"
            )

        return name


    
    # DISPLAY NAME
    
    def clean_display_name(self):
        name = self.cleaned_data.get("display_name", "")

        if not name:
            raise forms.ValidationError("Display name is required.")

        if len(name) > 50:
            raise forms.ValidationError("Display name cannot exceed 50 characters.")

        if not re.match(r'^[A-Za-z][A-Za-z\s&.\-]*$', name):
            raise forms.ValidationError(
                "Display name must start with a letter and contain only alphabets, spaces, &, . or -"
            )

        return name


    
    # EMAIL VALIDATION
    
    def clean_email(self):
        email = self.cleaned_data.get("email", "")

        if not email:
            raise forms.ValidationError("Email address is required.")

        email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$'

        if not re.match(email_regex, email):
            raise forms.ValidationError("Enter a valid email address.")

        return email


    
    # PHONE NUMBER
    
    def clean_mobile(self):
        mobile = self.cleaned_data.get("mobile", "")

        if not mobile:
            raise forms.ValidationError("Phone number is required.")

        if not mobile.isdigit():
            raise forms.ValidationError("Phone number must contain only digits.")

        if len(mobile) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        return mobile


    
    # ADDRESS
    
    def clean_address(self):
        address = self.cleaned_data.get("address", "")

        if not address:
            raise forms.ValidationError("Address is required.")

        if len(address) > 500:
            raise forms.ValidationError("Address cannot exceed 500 characters.")

        if not re.search(r'[A-Za-z]', address):
            raise forms.ValidationError("Address must contain meaningful text.")

        return address