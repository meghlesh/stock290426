from rest_framework import serializers
from .models import Stock,StockEntry
from rest_framework import serializers
from .models import ProductBatch, Product, Category, StockTransaction

class ExpiryWiseStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "item_name", "quantity", "price", "expiry_date"]
 

class StockValuationSerializer(serializers.ModelSerializer):
    avg_purchase_price = serializers.SerializerMethodField()
    total_purchase_value = serializers.SerializerMethodField()
    total_selling_value = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = ["id", "item_name", "quantity", "price", "avg_purchase_price", "total_purchase_value", "total_selling_value"]

    def get_avg_purchase_price(self, obj):
        entries = StockEntry.objects.filter(product__name=obj.item_name)
        if not entries.exists():
            return 0
        total_qty = sum([e.quantity_added for e in entries])
        if total_qty == 0:
            return 0
        total_cost = sum([float(e.quantity_added * e.purchase_price) for e in entries])
        return round(total_cost / total_qty, 2)

    def get_total_purchase_value(self, obj):
        avg_price = self.get_avg_purchase_price(obj)
        return round(obj.quantity * avg_price, 2)

    def get_total_selling_value(self, obj):
        return round(obj.quantity * float(obj.price), 2)
    
class OutOfStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ["id", "item_name", "quantity", "price", "expiry_date"]



class PurchaseStockReportSerializer(serializers.Serializer):
    product_name = serializers.CharField()
    category_name = serializers.CharField()
    total_quantity = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    period = serializers.DateField()




class ProductBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    category_name = serializers.CharField(source='product.category.name', read_only=True)
    days_to_expiry = serializers.SerializerMethodField()
    expiry_status = serializers.SerializerMethodField()
    batch_value = serializers.SerializerMethodField()

    class Meta:
        model = ProductBatch
        fields = [
            'id', 'batch_number', 'product_id', 'product_name', 'product_sku',
            'category_name', 'expiry_date', 'quantity', 'days_to_expiry',
            'expiry_status', 'batch_value', 'is_active', 'created_at'
        ]

    def get_days_to_expiry(self, obj):
        if obj.expiry_date:
            from datetime import date
            return (obj.expiry_date - date.today()).days
        return None

    def get_expiry_status(self, obj):
        return obj.expiry_status

    def get_batch_value(self, obj):
        """Calculate value of this batch based on purchase price"""
        if obj.product and obj.product.purchase_price:
            return float(obj.quantity * obj.product.purchase_price)
        return 0.0


class ExpiredStockReportSerializer(serializers.Serializer):
    total_expired_batches = serializers.IntegerField()
    total_expired_quantity = serializers.IntegerField()
    total_financial_loss = serializers.DecimalField(max_digits=12, decimal_places=2)
    expired_batches = ProductBatchSerializer(many=True)


class NearExpiryReportSerializer(serializers.Serializer):
    threshold_days = serializers.IntegerField()
    total_near_expiry_batches = serializers.IntegerField()
    total_quantity_at_risk = serializers.IntegerField()
    total_value_at_risk = serializers.DecimalField(max_digits=12, decimal_places=2)
    near_expiry_batches = serializers.ListField()


class FEFOComplianceSerializer(serializers.Serializer):
    total_sales_orders = serializers.IntegerField()
    fefo_compliant_orders = serializers.IntegerField()
    non_compliant_orders = serializers.IntegerField()
    compliance_percentage = serializers.FloatField()
    non_compliant_details = serializers.ListField()


class BlockedExpiredSalesSerializer(serializers.Serializer):
    total_blocked_attempts = serializers.IntegerField()
    blocked_sales = serializers.ListField()
    total_blocked_quantity = serializers.IntegerField()
    total_blocked_value = serializers.DecimalField(max_digits=12, decimal_places=2)


class LossDueToExpirySerializer(serializers.Serializer):
    total_loss_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_expired_quantity = serializers.IntegerField()
    loss_by_category = serializers.ListField()
    loss_by_product = serializers.ListField()
    loss_by_month = serializers.ListField()