from django import forms
from .models import Stock,Customer,Address,ContactPerson, Product
from .models import Quote, QuoteItem
from django.core.exceptions import ValidationError
from django import forms
import re
from .models import Customer
from django.core.validators import URLValidator
from datetime import date



class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ["item_name", "quantity", "price"]

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity")
        if qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero")
        return qty
    

class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = [
    "contact_name",
    "company_name",
    "customer_type",
    "email",
    "phone",
    "website",
    "currency",
    "payment_terms",
    "credit_limit",
    "gst_number",
    "place_of_supply",
    "notes",
]

        widgets = {
            "contact_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Contact Name",
                "required": True,
            }),

            "company_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Company Name",
                "required": True,
            }),

            "customer_type": forms.Select(attrs={
                "class": "form-select"
            }),

            "email": forms.EmailInput(attrs={
                "class": "form-control",
                "placeholder": "Email"
            }),

            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Phone"
            }),

            "website": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Website"
            }),

            "currency": forms.Select(
                choices=[("INR", "INR"), ("USD", "USD"), ("EUR", "EUR")],
                attrs={"class": "form-select"}
            ),

            "payment_terms": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Payment Terms"
            }),

            "credit_limit": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Credit Limit",
                "min": "0",
                "step": "0.01"
            }),

            "gst_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "GST Number"
            }),

            "place_of_supply": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Place of Supply"
            }),

            "notes": forms.Textarea(attrs={
                "class": "form-control",
                "placeholder":"Notes",
                "rows": 4
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        required_fields = [
            "contact_name",
            "company_name",
            "email",
            "phone",
            "website",
            "customer_type",
            "currency",
            "payment_terms",
            "credit_limit",
            "gst_number",
            "place_of_supply",
        ]

        for field in required_fields:
            if field in self.fields:
                self.fields[field].required = True

    def clean_contact_name(self):
        value = self.cleaned_data.get("contact_name", "").strip()
        if not value:
            raise forms.ValidationError("Contact name is required.")
        if not re.fullmatch(r"[A-Za-z]+( [A-Za-z]+)*", value):
            raise forms.ValidationError("Only alphabets allowed.")
        if len(value) > 20:
            raise forms.ValidationError("Maximum 20 characters allowed.")
        return value


    def clean_company_name(self):
        value = self.cleaned_data.get("company_name", "").strip()
        if not value:
            raise forms.ValidationError("Company name is required.")
        if not re.fullmatch(r"[A-Za-z0-9 ]+", value):
                raise forms.ValidationError("Only letters, numbers and inline spaces allowed.")
        return value


    def clean_phone(self):
        value = self.cleaned_data.get("phone", "")
        if not re.fullmatch(r"\d{10}", value):
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return value


    def clean_credit_limit(self):
        value = self.cleaned_data.get("credit_limit")
        if value is None or value < 0:
            raise forms.ValidationError("Credit limit must be positive.")
        return value


    def clean_gst_number(self):
        value = self.cleaned_data.get("gst_number", "").strip().upper()

        GST_REGEX = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"

        if not re.fullmatch(GST_REGEX, value):
            raise forms.ValidationError("Invalid GST format.")
        return value


def clean_website(self):
        value = self.cleaned_data.get("website", "").strip()

        if not value.startswith(("http://", "https://")):
            value = "https://" + value

        validator = URLValidator()
        try:
            validator(value)
        except ValidationError:
            raise forms.ValidationError("Enter valid URL (https://example.com)")
        return value

def clean_email(self):
    value = self.cleaned_data.get("email", "").strip()

    if not value:
        raise forms.ValidationError("Email is required.")

    if not re.fullmatch(r"[A-Za-z0-9._]+@[A-Za-z0-9.]+\.[A-Za-z]{2,}", value):
        raise forms.ValidationError("Enter a valid email address.")

    return value


class AddressForm(forms.ModelForm):
    address_type = forms.ChoiceField(
        choices=[('', 'Select Address Type')] + list(Address.ADDRESS_TYPE_CHOICES)
    )

    phone = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Phone",
            "maxlength": "10",
            "inputmode": "numeric"
        })
    )

    class Meta:
        model = Address
        fields = '__all__'

        widgets = {
            "attention": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Attention"
            }),
            "address_line1": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Address Line 1"
            }),
            "address_line2": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Address Line 2"
            }),

            "city": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "City",
                "maxlength": "30"
            }),


            "state": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "State"
            }),
            "country": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Country"
            }),
            "zip_code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Zip Code",
                "maxlength": "6"
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Phone",
                "maxlength": "10"
            }),
}

    #  CITY – alphabets only
    def clean_city(self):
            city = self.cleaned_data.get("city", "").strip()
            if not re.match(r'^[A-Za-z\s]+$', city):
                raise forms.ValidationError("City should contain only alphabets.")
            if len(city) > 30:
                raise forms.ValidationError("City cannot be more than 30 characters.")
            return city

    #  STATE – alphabets only
    def clean_state(self):
        state = self.cleaned_data.get("state", "").strip()
        if not re.match(r'^[A-Za-z\s]+$', state):
            raise forms.ValidationError("State should contain only alphabets.")
        return state

    #  COUNTRY – alphabets only
    def clean_country(self):
        country = self.cleaned_data.get("country", "").strip()
        if not re.match(r'^[A-Za-z\s]+$', country):
            raise forms.ValidationError("Country should contain only alphabets.")
        return country

     #  ZIP CODE – exactly 6 digits, numbers only, mandatory
    def clean_zip_code(self):
        zip_code = self.cleaned_data.get("zip_code", "").strip()

        # Condition 3: Mandatory field
        if not zip_code:
            raise forms.ValidationError("Zip Code is required.")

        # Condition 2: Numbers only
        if not zip_code.isdigit():
            raise forms.ValidationError("Zip Code should contain only numbers.")

        # Condition 1: Exactly 6 digits (India standard)
        if len(zip_code) != 6:
            raise forms.ValidationError("Zip Code must be exactly 6 digits.")

        return zip_code

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "").strip()

    # Condition 3: Mandatory field
        if not phone:
            raise forms.ValidationError("Phone number is required.")

    # Condition 2: Numbers only
        if not phone.isdigit():
            raise forms.ValidationError("Phone number should contain only numbers.")

    # Condition 1: Exactly 10 digits
        if len(phone) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")

        return phone




class ContactPersonForm(forms.ModelForm):

    salutation = forms.ChoiceField(
        choices=[
            ("Mr", "Mr"),
            ("Mrs", "Mrs"),
            ("Ms", "Ms"),
        ],
        initial="Mr",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    # phone = forms.CharField(required=True)

    class Meta:
        model = ContactPerson
        fields = "__all__"

        widgets = {
            "first_name": forms.TextInput(attrs={
                "class": "form-control validate-name",
                "placeholder": "First Name",
                "required": True
            }),
            "last_name": forms.TextInput(attrs={
                "class": "form-control validate-name",
                "placeholder": "Last Name",
                "required": True
            }),
            "email": forms.EmailInput(attrs={
                "class": "form-control validate-email",
                "placeholder": "Email",
                "required": True
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control validate-phone",
                "placeholder": "Phone",
                "maxlength": "10",
                "required": True
            }),
            "salutation": forms.Select(
                choices=[
                    ("", "Select"),
                    ("Mr", "Mr"),
                    ("Mrs", "Mrs"),
                    ("Ms", "Ms"),
                ],
                attrs={
                    "class": "form-select",
                    "required": True
                }
            ),
            "designation": forms.TextInput(attrs={
                "class": "form-control custom-text-only-content",
                "placeholder": "Designation",
                "required": True
            }),
            "customer": forms.Select(attrs={
                "class": "form-select",
                "required": True
            }),
            "is_primary": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }

    #  BACKEND VALIDATION (MANDATORY)

    def clean_first_name(self):
        value = self.cleaned_data.get("first_name")
        if not value.isalpha():
            raise forms.ValidationError("Only alphabets are allowed.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data.get("last_name")
        if value and not value.isalpha():
            raise forms.ValidationError("Only alphabets are allowed.")
        return value

    def clean_phone(self):
        phone = self.cleaned_data.get("phone")
        if not phone.isdigit():
            raise forms.ValidationError("Phone number must contain only digits.")
        if len(phone) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits.")
        return phone
    
    def clean_designation(self):
        value = self.cleaned_data.get("designation", "").strip()

        if not value:
            raise forms.ValidationError("Designation is required.")

        if not re.fullmatch(r"[A-Za-z ]+", value):
            raise forms.ValidationError("Only alphabets allowed in designation.")

        return value



class ProductForm(forms.ModelForm):
    default_expiry_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Product
        fields = ['name', 'product_company', 'sku', 'category', 'purchase_price', 'selling_price', 
                 'stock_quantity', 'is_expiry_tracked', 'default_expiry_date']
        widgets = {
            'name': forms.TextInput(attrs={'maxlength': '50'}),
            'product_company': forms.TextInput(attrs={'maxlength': '100'}),
            'purchase_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'selling_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if len(name) < 2:
            raise ValidationError('Product name must be at least 2 characters long')
        if self.company and Product.objects.filter(
            company=self.company, 
            name__iexact=name
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Product name already exists')
        return name

    def clean_sku(self):
        sku = self.cleaned_data['sku'].strip().upper()
        if len(sku) < 3:
            raise ValidationError('SKU must be at least 3 characters long')
        if self.company and Product.objects.filter(
            company=self.company,
            sku__iexact=sku
        ).exclude(pk=self.instance.pk).exists():
            raise ValidationError('SKU code already exists')
        return sku

    def clean_category(self):
        category = self.cleaned_data.get('category')
        if not category:
            raise ValidationError('Please select a category')
        return category

    def clean_purchase_price(self):
        price = self.cleaned_data['purchase_price']
        if price <= 0:
            raise ValidationError('Purchase price must be greater than 0')
        return price

    def clean_selling_price(self):
        price = self.cleaned_data['selling_price']
        purchase_price = self.cleaned_data.get('purchase_price', 0)
        if price <= 0:
            raise ValidationError('Selling price must be greater than 0')
        if price <= purchase_price:
            raise ValidationError('Selling price must be greater than purchase price')
        return price

    def clean_stock_quantity(self):
        quantity = self.cleaned_data.get('stock_quantity')
        return quantity or 0

def clean(self):
    cleaned_data = super().clean()
    is_expiry_tracked = cleaned_data.get('is_expiry_tracked', False)

    expiry_date = cleaned_data.get('expiry_date') or cleaned_data.get('default_expiry_date')

    if is_expiry_tracked and not expiry_date:
        raise ValidationError({'expiry_date': ['Expiry date required when tracking enabled']})

    name = cleaned_data.get('name')
    if name and len(name) > 50:
        raise ValidationError({'name': ['Name must be max 50 characters']})

    return cleaned_data
    


from django import forms
from django.forms import inlineformset_factory


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = [
            'customer', 'reference_number', 'quote_date', 'expiry_date',
            'salesperson', 'project_name', 'subject',
            'customer_notes', 'terms'
        ]
        widgets = {
            'quote_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


QuoteItemFormSet = inlineformset_factory(
    Quote,
    QuoteItem,
    fields=['product', 'quantity', 'rate'],
    extra=1,
    can_delete=True
)


from .models import PurchaseOrderItem

class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = "__all__"

    def clean_cost_price(self):
        price = self.cleaned_data.get("cost_price")
        if price <= 0:
            raise ValidationError("Cost price must be greater than 0")
        return price
    
    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')

        if expiry_date and expiry_date < date.today():
            raise ValidationError("Expiry date cannot be in the past.")
        
        return expiry_date
    
    def clean(self):
        cleaned_data = super().clean()
        expiry_date = cleaned_data.get('expiry_date')

        from datetime import date
        if expiry_date and expiry_date < date.today():
            raise ValidationError("Expiry date cannot be in the past.")

        return cleaned_data

    
