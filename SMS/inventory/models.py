from django.db import models
from company.models import Company
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.db.models import Sum, F, DecimalField
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator




class Category(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Product(models.Model):

    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True
    )

    name = models.CharField(max_length=50)

    product_company = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Manufacturer/Brand name"
    )

    sku = models.CharField(
        max_length=100,
        unique=True
    )

    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_expiry_tracked = models.BooleanField(default=False)

    stock_quantity = models.IntegerField(default=0)

    low_stock_limit = models.IntegerField(default=5)

    # NEW FIELD FOR ABC CLASSIFICATION
    abc_class = models.CharField(
        max_length=1,
        choices=[
            ("A", "A - High Value"),
            ("B", "B - Medium Value"),
            ("C", "C - Low Value"),
        ],
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'name')

    def __str__(self):
        return self.name

    
    # LOW STOCK CHECK
    

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_limit

    
    # TOTAL STOCK FROM BATCHES
    

    @property
    def total_stock(self):
        return (
            self.productbatch_set
            .aggregate(total=Sum('quantity'))
            ['total'] or 0
        )

    
    # STOCK VALUATION
    

    @property
    def stock_valuation(self):
        """
        Total inventory value for this product
        (Based on available, non-expired batch stock)
        """

        return (
            self.productbatch_set
            .filter(
                quantity__gt=0,
                expiry_date__gte=date.today()
            )
            .aggregate(
                value=Sum(
                    F("quantity") * F("product__purchase_price"),
                    output_field=DecimalField()
                )
            )["value"] or 0
        )

    
    # INVENTORY VALUE (FOR ABC)
    

    @property
    def inventory_value(self):
        """
        Used for ABC classification
        """

        return self.stock_quantity * self.purchase_price
    
class SalesOrder(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    order_number = models.CharField(max_length=20, unique=True)
    customer_name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_number


class SalesOrderItem(models.Model):
    order = models.ForeignKey(SalesOrder, related_name="items", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"
    

class Vendor(models.Model):

    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    STATUS_CHOICES = (
        ('A', 'Active'),
        ('I', 'Inactive'),
    )

    status = models.CharField(
        max_length=1,
        choices=STATUS_CHOICES,
        default='A'
    )

    # Contact person
    salutation = models.CharField(
        max_length=10,
        choices=[
            ("Mr", "Mr"),
            ("Mrs", "Mrs"),
            ("Ms", "Ms"),
        ],
        blank=True,
        null=True
    )

    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)

    # Vendor identity
    company_name = models.CharField(max_length=150, blank=True, null=True)
    display_name = models.CharField(max_length=150)

    #  ADD THIS FIELD
    gst_number = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        unique=True
    )

    # Contact
    email = models.EmailField(blank=True, null=True)
    mobile = models.CharField(max_length=20, blank=True, null=True)
    work_phone = models.CharField(max_length=20, blank=True, null=True)

    # Preferences
    language = models.CharField(
        max_length=50,
        default="English",
        blank=True,
        null=True
    )

    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.display_name

    

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("ORDERED", "Ordered"),
        ("PARTIAL", "Partially Received"),  #  NEW
        ("RECEIVED", "Received"),
        ("CANCELLED", "Cancelled"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)

    order_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="DRAFT"
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.order_number or "PO (unsaved)"



class PurchaseOrderItem(models.Model):
    order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE
    )

    quantity = models.PositiveIntegerField()

    #  NEW FIELD (MAIN CHANGE)
    received_quantity = models.PositiveIntegerField(default=0)

    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )

    batch_number = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    expiry_date = models.DateField(
        null=True,
        blank=True
    )

    
    # CALCULATED FIELDS
    

    @property
    def subtotal(self):
        return self.quantity * self.cost_price

    @property
    def remaining_quantity(self):
        return self.quantity - self.received_quantity

    
    # VALIDATION
    

    def clean(self):
        super().clean()

        #  Fix: use order.company (not self.company)
        if self.batch_number:
            exists = ProductBatch.objects.filter(
                company=self.order.company,
                product=self.product,
                batch_number__iexact=self.batch_number
            ).exclude(pk=self.pk).exists()

            if exists:
                raise ValidationError({
                    "batch_number": "This batch number already exists for this product."
                })

    
    # STRING REPRESENTATION
    

    def __str__(self):
        return f"{self.product.name} | {self.batch_number or 'NO-BATCH'}"
    


class Stock(models.Model):
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.item_name


class StockEntry(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    product = models.ForeignKey(
        Product,
        related_name="stock_entries",
        on_delete=models.CASCADE
    )

    quantity_added = models.PositiveIntegerField()

    purchase_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} +{self.quantity_added}"

class Customer(models.Model):
    CUSTOMER_TYPE_CHOICES = [
        ('business', 'Business'),
        ('individual', 'Individual'),
    ]

    contact_name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True, null=True)

    company = models.ForeignKey(   
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    customer_type = models.CharField(
        max_length=20,
        choices=CUSTOMER_TYPE_CHOICES,
        default='business'
    )

    email = models.EmailField(blank=True, null=True, unique=True)  #  Added unique
    phone = models.CharField(max_length=20, blank=True, null=True, unique=True) # Added unique
    website = models.URLField(blank=True, null=True, unique=True)  #  Added unique

    currency = models.CharField(max_length=10, default='INR')
    payment_terms = models.CharField(max_length=100, blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    gst_number = models.CharField(max_length=20, blank=True, null=True, unique=True)  #  Added unique
    place_of_supply = models.CharField(max_length=100, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contact_name', 'company_name'], 
                name='unique_customer_name_company'
            )
        ]

    def __str__(self):
        return self.contact_name

    def clean(self):
        super().clean()
        errors = {}
        
        #  Validate unique contact_name + company_name combination
        if self.contact_name and self.company_name:
            existing = Customer.objects.filter(
                contact_name__iexact=self.contact_name,
                company_name__iexact=self.company_name
            ).exclude(pk=self.pk).exists()
            
            if existing:
                errors['contact_name'] = 'A customer with this name and company already exists.'
        # Validate unique phone number
        if self.phone:
            # Clean phone number (remove spaces, dashes, etc.)
            clean_phone = ''.join(filter(str.isdigit, self.phone))
            
            # Check for duplicates
            existing = Customer.objects.filter(phone__icontains=clean_phone).exclude(pk=self.pk).exists()
            
            if existing:
                errors['phone'] = 'A customer with this phone number already exists.'
        #  Validate unique email
        if self.email:
            existing = Customer.objects.filter(
                email__iexact=self.email
            ).exclude(pk=self.pk).exists()
            
            if existing:
                errors['email'] = 'A customer with this email already exists.'
        
        #  Validate unique website
        if self.website:
            existing = Customer.objects.filter(
                website__iexact=self.website
            ).exclude(pk=self.pk).exists()
            
            if existing:
                errors['website'] = 'A customer with this website already exists.'
        
        #  Validate unique GST number
        if self.gst_number:
            existing = Customer.objects.filter(
                gst_number__iexact=self.gst_number
            ).exclude(pk=self.pk).exists()
            
            if existing:
                errors['gst_number'] = 'A customer with this GST number already exists.'
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Clean phone number before saving
        if self.phone:
            self.phone = ''.join(filter(str.isdigit, self.phone))
        self.full_clean()
        super().save(*args, **kwargs)


class Address(models.Model):

    ADDRESS_TYPE_CHOICES = [
        ('billing', 'Billing'),
        ('shipping', 'Shipping'),
    ]

    address_type = models.CharField(
        max_length=20,
        choices=ADDRESS_TYPE_CHOICES
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    address_type = models.CharField(max_length=10, choices=ADDRESS_TYPE_CHOICES)

    attention = models.CharField(max_length=100, blank=True)
    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)

    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="India")

    phone = models.CharField(max_length=20, blank=True)

    is_default = models.BooleanField(default=False)

    # created_at = models.DateTimeField(auto_now_add=True)
    
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer} - {self.address_type}"


class ContactPerson(models.Model):
    SALUTATION_CHOICES = (
        ("Mr", "Mr"),
        ("Mrs", "Mrs"),
        ("Ms", "Ms"),
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='contact_persons'
    )

    salutation = models.CharField(max_length=10, blank=True, choices=SALUTATION_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)

    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    designation = models.CharField(max_length=100, blank=True)

    is_primary = models.BooleanField(default=False)

    # created_at = models.DateTimeField(auto_now_add=True)
    
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StockTransaction(models.Model):

    TRANSACTION_TYPE = (
        ('IN', 'Stock In'),
        ('OUT', 'Stock Out'),
    )

    SOURCE_TYPE = (
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('MANUAL', 'Manual Adjustment'),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    #  FEFO AUDIT FIELD (NEW)
    batch = models.ForeignKey(
        "ProductBatch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Batch used for this transaction (FEFO tracking)"
    )

    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_TYPE
    )

    quantity = models.PositiveIntegerField()
    reference_number = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.product.name} | "
            f"{self.transaction_type} | "
            f"{self.quantity} | "
            f"Batch: {self.batch.batch_number if self.batch else 'N/A'}"
        )






class Quote(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('expired', 'Expired'),
    ]

    quote_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    reference_number = models.CharField(max_length=100, blank=True, null=True)

    quote_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(blank=True, null=True)

    salesperson = models.CharField(max_length=100, blank=True, null=True)
    project_name = models.CharField(max_length=150, blank=True, null=True)

    subject = models.TextField(blank=True, null=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    customer_notes = models.TextField(blank=True, null=True)
    terms = models.TextField(blank=True, null=True)
    attachments = models.FileField(upload_to='quotes/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.quote_number


class QuoteItem(models.Model):
    quote = models.ForeignKey(
        Quote, related_name="items", on_delete=models.CASCADE
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.product.name
    



from datetime import date, timedelta

class ProductBatch(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)

    #  OPTIONAL for non-expiry products
    batch_number = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    expiry_date = models.DateField(
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('company', 'product', 'batch_number')

    def __str__(self):
        return f"{self.product.name} | {self.batch_number or 'NO-BATCH'}"

    # 🔽 SAFE PROPERTIES (NO CRASH)
    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        return date.today() <= self.expiry_date <= date.today() + timedelta(days=30)

    @property
    def expiry_status(self):
        if not self.expiry_date:
            return "NO_EXPIRY"
        if self.is_expired:
            return "EXPIRED"
        elif self.is_near_expiry:
            return "NEAR_EXPIRY"
        return "SAFE"
    


class InventoryAlert(models.Model):
    SEVERITY_CHOICES = (
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    batch = models.ForeignKey(ProductBatch, on_delete=models.CASCADE, null=True, blank=True)

    alert_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    message = models.TextField()

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alert_type} | {self.severity}"
    
