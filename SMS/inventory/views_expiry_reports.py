from datetime import date, timedelta
from django.db.models import Sum, Q, F, Count, Value, DecimalField, Case, When
from django.db.models.functions import TruncMonth
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from accounts.models import UserProfile
from inventory.models import ProductBatch, Product, Category, StockTransaction, SalesOrder, SalesOrderItem
from inventory.serializers import (
    ProductBatchSerializer, 
    ExpiredStockReportSerializer,
    NearExpiryReportSerializer,
    FEFOComplianceSerializer,
    BlockedExpiredSalesSerializer,
    LossDueToExpirySerializer
)


# 1. NEAR-EXPIRY PRODUCTS REPORT
# Configurable threshold (30/60/90 days)
class NearExpiryProductsReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/near-expiry-products/
    
    Query Parameters:
        - days: Threshold days (default: 30, options: 30, 60, 90)
        - category_id: Filter by category (optional)
        - product_id: Filter by product (optional)
        - company_id: Admin only - filter by company
    
    Returns:
        - List of products/batches near expiry
        - Summary statistics
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                # Admin can view any company
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get threshold days (default: 30)
        try:
            days = int(request.GET.get('days', 30))
            if days not in [30, 60, 90]:
                days = 30  # Default to 30 if invalid
        except ValueError:
            days = 30

        # Get filter parameters
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        
        today = date.today()
        expiry_limit = today + timedelta(days=days)

        # Base queryset
        batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__isnull=False,
            expiry_date__gte=today,  # Not expired yet
            expiry_date__lte=expiry_limit,  # Within threshold
            quantity__gt=0,
            is_active=True
        ).select_related('product', 'product__category').order_by('expiry_date')

        # Apply filters
        if category_id:
            batches = batches.filter(product__category_id=category_id)
        
        if product_id:
            batches = batches.filter(product_id=product_id)

        # Calculate summary
        total_quantity_at_risk = batches.aggregate(
            total=Sum('quantity')
        )['total'] or 0

        total_value_at_risk = 0
        for batch in batches:
            if batch.product and batch.product.purchase_price:
                total_value_at_risk += batch.quantity * float(batch.product.purchase_price)

        # Prepare batch data
        batch_data = []
        for batch in batches:
            days_left = (batch.expiry_date - today).days
            batch_data.append({
                'batch_id': batch.id,
                'batch_number': batch.batch_number or 'NO-BATCH',
                'product_id': batch.product.id,
                'product_name': batch.product.name,
                'product_sku': batch.product.sku,
                'category': batch.product.category.name if batch.product.category else 'Uncategorized',
                'category_id': batch.product.category.id if batch.product.category else None,
                'expiry_date': batch.expiry_date,
                'expiry_date_formatted': batch.expiry_date.strftime('%d-%b-%Y'),
                'days_left': days_left,
                'quantity': batch.quantity,
                'purchase_price': float(batch.product.purchase_price) if batch.product.purchase_price else 0,
                'selling_price': float(batch.product.selling_price) if batch.product.selling_price else 0,
                'batch_value': batch.quantity * float(batch.product.purchase_price) if batch.product.purchase_price else 0,
                'risk_level': 'HIGH' if days_left <= 15 else 'MEDIUM' if days_left <= 30 else 'LOW'
            })

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'threshold_days': days,
            'summary': {
                'total_near_expiry_batches': batches.count(),
                'total_quantity_at_risk': total_quantity_at_risk,
                'total_value_at_risk': round(total_value_at_risk, 2),
                'categories_affected': batches.values('product__category__name').distinct().count(),
                'products_affected': batches.values('product').distinct().count(),
            },
            'near_expiry_batches': batch_data,
            'filters_applied': {
                'days': days,
                'category_id': category_id,
                'product_id': product_id
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)


# 2. EXPIRED STOCK REPORT
class ExpiredStockReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/expired-stock/
    
    Query Parameters:
        - category_id: Filter by category
        - product_id: Filter by product
        - include_disposed: Include already disposed stock (default: false)
        - company_id: Admin only - filter by company
    
    Returns:
        - List of expired batches with value
        - Financial loss calculation
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        include_disposed = request.GET.get('include_disposed', 'false').lower() == 'true'

        # Base queryset - expired batches with stock
        batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0
        ).select_related('product', 'product__category')

        if not include_disposed:
            batches = batches.filter(is_active=True)

        # Apply filters
        if category_id:
            batches = batches.filter(product__category_id=category_id)
        
        if product_id:
            batches = batches.filter(product_id=product_id)

        batches = batches.order_by('expiry_date')

        # Calculate financial loss
        total_loss = 0
        batch_data = []

        for batch in batches:
            days_expired = (today - batch.expiry_date).days
            purchase_price = float(batch.product.purchase_price) if batch.product.purchase_price else 0
            batch_loss = batch.quantity * purchase_price
            total_loss += batch_loss

            batch_data.append({
                'batch_id': batch.id,
                'batch_number': batch.batch_number or 'NO-BATCH',
                'product_id': batch.product.id,
                'product_name': batch.product.name,
                'product_sku': batch.product.sku,
                'category': batch.product.category.name if batch.product.category else 'Uncategorized',
                'expiry_date': batch.expiry_date,
                'expiry_date_formatted': batch.expiry_date.strftime('%d-%b-%Y'),
                'days_expired': days_expired,
                'quantity': batch.quantity,
                'purchase_price': purchase_price,
                'selling_price': float(batch.product.selling_price) if batch.product.selling_price else 0,
                'financial_loss': round(batch_loss, 2),
                'is_active': batch.is_active,
                'received_date': batch.created_at.date() if batch.created_at else None
            })

        # Loss by category
        loss_by_category = []
        categories = batches.values('product__category__name').annotate(
            total_quantity=Sum('quantity'),
            total_loss=Sum(F('quantity') * F('product__purchase_price'), output_field=DecimalField())
        ).order_by('-total_loss')

        for cat in categories:
            loss_by_category.append({
                'category': cat['product__category__name'] or 'Uncategorized',
                'total_quantity': cat['total_quantity'] or 0,
                'total_loss': round(float(cat['total_loss'] or 0), 2)
            })

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'summary': {
                'total_expired_batches': batches.count(),
                'total_expired_quantity': batches.aggregate(total=Sum('quantity'))['total'] or 0,
                'total_financial_loss': round(total_loss, 2),
                'categories_affected': len(loss_by_category),
                'products_affected': batches.values('product').distinct().count(),
            },
            'loss_by_category': loss_by_category,
            'expired_batches': batch_data,
            'filters_applied': {
                'category_id': category_id,
                'product_id': product_id,
                'include_disposed': include_disposed
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)



# 3. FEFO COMPLIANCE REPORT

class FEFOComplianceReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/fefo-compliance/
    
    Checks if sales orders are using FEFO principle
    (First Expiry First Out - oldest expiry first)
    
    Query Parameters:
        - from_date: Start date (YYYY-MM-DD)
        - to_date: End date (YYYY-MM-DD)
        - company_id: Admin only - filter by company
    
    Returns:
        - Compliance percentage
        - Non-compliant orders details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Date filters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        today = date.today()

        # Base sales orders queryset
        orders = SalesOrder.objects.filter(
            company=company,
            status__in=['DELIVERED', 'PROCESSING']
        )

        if from_date:
            orders = orders.filter(created_at__date__gte=from_date)
        if to_date:
            orders = orders.filter(created_at__date__lte=to_date)

        total_orders = orders.count()
        compliant_orders = 0
        non_compliant_details = []

        # Check each order for FEFO compliance
        for order in orders:
            order_items = SalesOrderItem.objects.filter(order=order).select_related('product')
            is_compliant = True
            order_violations = []

            for item in order_items:
                product = item.product
                
                # Get transactions for this order item
                transactions = StockTransaction.objects.filter(
                    company=company,
                    product=product,
                    reference_number=order.order_number,
                    transaction_type='OUT',
                    source='SALE'
                ).select_related('batch').order_by('created_at')

                # Get available batches at order time
                available_batches = ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=order.created_at.date() if order.created_at else today,
                    quantity__gt=0,
                    is_active=True
                ).order_by('expiry_date')

                earliest_batch = available_batches.first()
                
                for txn in transactions:
                    if txn.batch and earliest_batch:
                        # Check if they used the earliest expiry batch
                        if txn.batch.expiry_date != earliest_batch.expiry_date:
                            is_compliant = False
                            order_violations.append({
                                'product': product.name,
                                'used_batch': txn.batch.batch_number,
                                'used_expiry': txn.batch.expiry_date.strftime('%Y-%m-%d'),
                                'should_use_batch': earliest_batch.batch_number,
                                'should_use_expiry': earliest_batch.expiry_date.strftime('%Y-%m-%d'),
                                'quantity': txn.quantity
                            })

            if is_compliant:
                compliant_orders += 1
            else:
                non_compliant_details.append({
                    'order_id': order.id,
                    'order_number': order.order_number,
                    'order_date': order.created_at.date().strftime('%Y-%m-%d'),
                    'customer': order.customer_name,
                    'violations': order_violations[:5]  # Limit to 5 violations per order
                })

        compliance_percentage = (compliant_orders / total_orders * 100) if total_orders > 0 else 0

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'date_range': {
                'from': from_date or 'All',
                'to': to_date or 'All'
            },
            'summary': {
                'total_sales_orders': total_orders,
                'fefo_compliant_orders': compliant_orders,
                'non_compliant_orders': total_orders - compliant_orders,
                'compliance_percentage': round(compliance_percentage, 2),
                'compliance_grade': self._get_compliance_grade(compliance_percentage)
            },
            'non_compliant_orders': non_compliant_details[:20]  # Limit to 20 orders
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _get_compliance_grade(self, percentage):
        if percentage >= 95:
            return 'A - Excellent'
        elif percentage >= 85:
            return 'B - Good'
        elif percentage >= 70:
            return 'C - Average'
        elif percentage >= 50:
            return 'D - Poor'
        else:
            return 'F - Critical'



# 4. BLOCKED EXPIRED STOCK SALES REPORT

class BlockedExpiredSalesReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/blocked-expired-sales/
    
    Tracks attempts to sell expired stock that were blocked
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - company_id: Admin only - filter by company
    
    Returns:
        - List of blocked sales attempts
        - Total prevented loss
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )


        
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        today = date.today()

        # Get out-of-stock alerts that might indicate blocked sales
        from inventory.models import InventoryAlert
        
        alerts = InventoryAlert.objects.filter(
            company=company,
            alert_type='OUT_OF_STOCK',
            created_at__date__gte=from_date if from_date else today - timedelta(days=90),
            created_at__date__lte=to_date if to_date else today
        ).select_related('product').order_by('-created_at')

        blocked_sales = []
        total_blocked_value = 0
        total_blocked_quantity = 0

        for alert in alerts[:100]:  # Limit to 100 most recent
            if alert.product:
                # Estimate blocked sale value
                sale_value = float(alert.product.selling_price) * 1  # Assume 1 unit attempt
                total_blocked_value += sale_value
                total_blocked_quantity += 1

                blocked_sales.append({
                    'alert_id': alert.id,
                    'date': alert.created_at.date().strftime('%Y-%m-%d'),
                    'product_id': alert.product.id,
                    'product_name': alert.product.name,
                    'product_sku': alert.product.sku,
                    'message': alert.message,
                    'estimated_sale_value': round(sale_value, 2),
                    'prevented_loss': round(sale_value, 2)  # Same as sale value
                })

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'summary': {
                'total_blocked_attempts': len(blocked_sales),
                'total_blocked_quantity': total_blocked_quantity,
                'total_prevented_loss': round(total_blocked_value, 2),
                'unique_products_affected': len(set([b['product_id'] for b in blocked_sales]))
            },
            'blocked_sales': blocked_sales,
            'filters_applied': {
                'from_date': from_date,
                'to_date': to_date
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)



# 5. LOSS DUE TO EXPIRY (VALUE-BASED)

class LossDueToExpiryReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/loss-due-to-expiry/
    
    Comprehensive financial loss report due to expired stock
    
    Query Parameters:
        - period: 'monthly', 'quarterly', 'yearly' (default: monthly)
        - category_id: Filter by category
        - from_date: Custom start date
        - to_date: Custom end date
        - company_id: Admin only - filter by company
    
    Returns:
        - Total financial loss
        - Loss breakdown by category, product, time period
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        period = request.GET.get('period', 'monthly')
        category_id = request.GET.get('category_id')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')

        # Date range for expired batches
        if from_date:
            start_date = from_date
        else:
            # Default to last 12 months
            start_date = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        
        if to_date:
            end_date = to_date
        else:
            end_date = today.strftime('%Y-%m-%d')

        # Get expired batches
        batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0
        ).select_related('product', 'product__category')

        # Apply date filter based on when they expired
        batches = batches.filter(expiry_date__gte=start_date, expiry_date__lte=end_date)

        if category_id:
            batches = batches.filter(product__category_id=category_id)

        # Calculate total loss
        total_loss = 0
        total_quantity = 0

        for batch in batches:
            if batch.product and batch.product.purchase_price:
                total_loss += batch.quantity * float(batch.product.purchase_price)
                total_quantity += batch.quantity

        # Loss by category
        loss_by_category = []
        categories = batches.values('product__category__name', 'product__category__id').annotate(
            total_quantity=Sum('quantity'),
            total_loss=Sum(F('quantity') * F('product__purchase_price'), output_field=DecimalField()),
            batch_count=Count('id')
        ).order_by('-total_loss')

        for cat in categories:
            loss_by_category.append({
                'category_id': cat['product__category__id'],
                'category_name': cat['product__category__name'] or 'Uncategorized',
                'total_quantity': cat['total_quantity'] or 0,
                'total_loss': round(float(cat['total_loss'] or 0), 2),
                'batch_count': cat['batch_count'],
                'percentage_of_total': round((float(cat['total_loss'] or 0) / total_loss * 100), 2) if total_loss > 0 else 0
            })

        # Loss by product (top 20)
        loss_by_product = []
        products = batches.values(
            'product__id', 'product__name', 'product__sku', 'product__category__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_loss=Sum(F('quantity') * F('product__purchase_price'), output_field=DecimalField()),
            batch_count=Count('id')
        ).order_by('-total_loss')[:20]

        for prod in products:
            loss_by_product.append({
                'product_id': prod['product__id'],
                'product_name': prod['product__name'],
                'product_sku': prod['product__sku'],
                'category': prod['product__category__name'] or 'Uncategorized',
                'total_quantity': prod['total_quantity'] or 0,
                'total_loss': round(float(prod['total_loss'] or 0), 2),
                'batch_count': prod['batch_count']
            })

        # Loss by month
        loss_by_month = []
        
        if period == 'monthly':
            monthly_loss = batches.annotate(
                month=TruncMonth('expiry_date')
            ).values('month').annotate(
                total_quantity=Sum('quantity'),
                total_loss=Sum(F('quantity') * F('product__purchase_price'), output_field=DecimalField()),
                batch_count=Count('id')
            ).order_by('-month')

            for ml in monthly_loss[:24]:  # Last 24 months
                if ml['month']:
                    loss_by_month.append({
                        'period': ml['month'].strftime('%Y-%m'),
                        'period_formatted': ml['month'].strftime('%b %Y'),
                        'total_quantity': ml['total_quantity'] or 0,
                        'total_loss': round(float(ml['total_loss'] or 0), 2),
                        'batch_count': ml['batch_count']
                    })

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'date_range': {
                'from': start_date,
                'to': end_date
            },
            'summary': {
                'total_financial_loss': round(total_loss, 2),
                'total_expired_quantity': total_quantity,
                'total_expired_batches': batches.count(),
                'categories_affected': len(loss_by_category),
                'products_affected': batches.values('product').distinct().count(),
                'avg_loss_per_batch': round(total_loss / batches.count(), 2) if batches.count() > 0 else 0
            },
            'loss_by_category': loss_by_category,
            'loss_by_product': loss_by_product,
            'loss_over_time': loss_by_month,
            'filters_applied': {
                'period': period,
                'category_id': category_id,
                'from_date': from_date,
                'to_date': to_date
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)



# 6. EXPIRY SUMMARY DASHBOARD API

class ExpirySummaryDashboardAPIView(APIView):
    """
    API: GET /inventory/api/reports/expiry-summary/
    
    Combined expiry summary for dashboard
    
    Returns:
        - All expiry metrics in one API call
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            if request.user.is_superuser and request.GET.get('company_id'):
                from company.models import Company
                company = Company.objects.get(id=request.GET.get('company_id'))
            else:
                profile = UserProfile.objects.select_related("company").get(user=request.user)
                company = profile.company
        except (UserProfile.DoesNotExist, Company.DoesNotExist):
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        
        # Thresholds for near expiry
        thresholds = {
            '30_days': today + timedelta(days=30),
            '60_days': today + timedelta(days=60),
            '90_days': today + timedelta(days=90)
        }

        # 1. Expired stock summary
        expired_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0,
            is_active=True
        )
        
        expired_count = expired_batches.count()
        expired_quantity = expired_batches.aggregate(total=Sum('quantity'))['total'] or 0
        
        expired_loss = 0
        for batch in expired_batches:
            if batch.product and batch.product.purchase_price:
                expired_loss += batch.quantity * float(batch.product.purchase_price)

        # 2. Near expiry by threshold
        near_expiry_counts = {}
        near_expiry_quantities = {}
        
        for label, limit_date in thresholds.items():
            batches = ProductBatch.objects.filter(
                company=company,
                expiry_date__gte=today,
                expiry_date__lte=limit_date,
                quantity__gt=0,
                is_active=True
            )
            near_expiry_counts[label] = batches.count()
            near_expiry_quantities[label] = batches.aggregate(total=Sum('quantity'))['total'] or 0

        # 3. Total active batches
        active_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__gte=today,
            quantity__gt=0,
            is_active=True
        )
        active_count = active_batches.count()
        active_quantity = active_batches.aggregate(total=Sum('quantity'))['total'] or 0

        # 4. Products with near expiry
        products_near_expiry = Product.objects.filter(
            company=company,
            productbatch__expiry_date__range=[today, thresholds['30_days']],
            productbatch__quantity__gt=0,
            productbatch__is_active=True
        ).distinct().count()

        response_data = {
            'status': 'success',
            'company': company.name,
            'report_date': today.strftime('%Y-%m-%d'),
            'expiry_summary': {
                'expired': {
                    'batch_count': expired_count,
                    'total_quantity': expired_quantity,
                    'financial_loss': round(expired_loss, 2)
                },
                'near_expiry': {
                    '30_days': {
                        'batch_count': near_expiry_counts.get('30_days', 0),
                        'total_quantity': near_expiry_quantities.get('30_days', 0)
                    },
                    '60_days': {
                        'batch_count': near_expiry_counts.get('60_days', 0),
                        'total_quantity': near_expiry_quantities.get('60_days', 0)
                    },
                    '90_days': {
                        'batch_count': near_expiry_counts.get('90_days', 0),
                        'total_quantity': near_expiry_quantities.get('90_days', 0)
                    }
                },
                'healthy_stock': {
                    'batch_count': active_count - near_expiry_counts.get('90_days', 0),
                    'total_quantity': active_quantity - near_expiry_quantities.get('90_days', 0)
                }
            },
            'metrics': {
                'products_near_expiry_30d': products_near_expiry,
                'expiry_rate': round((expired_count / (active_count + expired_count) * 100), 2) if (active_count + expired_count) > 0 else 0,
                'total_batches_managed': active_count + expired_count
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)