from django.db import models
from django.contrib.auth.models import User
from django.db import models
from django.core.exceptions import ValidationError
import re

 


class Company(models.Model):
    name = models.CharField(max_length=50, unique=True)
    email = models.EmailField()
    owner = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company_owner"
    )
    created_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.name
    
class Transaction(models.Model):
    STATUS_CHOICES = (
        ("DELIVERED", "Delivered"),
        ("PROCESSING", "Processing"),
        ("CANCELLED", "Cancelled"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    ref_id = models.CharField(max_length=20, unique=True)
    item_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ref_id
    

def validate_name(value):
    value = value.strip()

    if not value:
        raise ValidationError("This field cannot be empty.")

    if len(value) > 20:
        raise ValidationError("Maximum 20 characters allowed.")

    if not re.match(r'^[A-Za-z]+$', value):
        raise ValidationError("Only alphabetic characters are allowed.")


def validate_name(value):
    if not re.match(r'^[A-Za-z]+$', value):
        raise ValidationError("Only alphabetic characters are allowed.")

def validate_name(value):
    if not re.match(r'^[A-Za-z]+$', value):
        raise ValidationError("Only alphabetic characters are allowed.")

def validate_name(value):
    if not re.match(r'^[A-Za-z]+$', value):
        raise ValidationError("Only alphabetic characters are allowed.")


def validate_gst(value):
    gst_regex = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$'
    if not re.match(gst_regex, value):
        raise ValidationError("Invalid GST format (Example: 22AAAAA0000A1Z5)")


class Vendor(models.Model):

    company = models.ForeignKey(
        'Company',
        on_delete=models.CASCADE,
        related_name='vendors',
        null=True, blank=True
    )

    salutation = models.CharField(
        max_length=10,
        blank=True,
        null=True
    )

    primary_contact_first_name = models.CharField(
        max_length=20,
        validators=[validate_name]
    )

    primary_contact_last_name = models.CharField(
        max_length=20,
        validators=[validate_name]
    )

    company_name = models.CharField(
        max_length=100,
        db_index=True
    )

    display_name = models.CharField(
        max_length=100
    )

    gst_number = models.CharField(
        max_length=15,
        validators=[validate_gst],
        db_index=True,
        blank=True,
        null=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    mobile = models.CharField(
        max_length=10
    )

    language = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    address = models.TextField(
        max_length=300
    )

    
    # SYSTEM FIELDS
    

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    
    # META OPTIONS
    

    class Meta:
        unique_together = ['company', 'gst_number']
        ordering = ['company_name']
        indexes = [
            models.Index(fields=['company']),
            models.Index(fields=['gst_number']),
        ]

    
    # SAVE METHOD
    

    def save(self, *args, **kwargs):

        if self.gst_number:
            self.gst_number = self.gst_number.upper().strip()

        self.full_clean()
        super().save(*args, **kwargs)

    
    # STRING REPRESENTATION
    

    def __str__(self):
        return f"{self.company_name} - {self.display_name}"



class Staff(models.Model):
    company = models.ForeignKey(
        "Company",
        on_delete=models.CASCADE,
        related_name="staff"
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

from django.db import models
from company.models import Company

class NewEntry(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    entry_name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.entry_name