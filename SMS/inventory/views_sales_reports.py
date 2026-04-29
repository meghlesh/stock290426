from django.db import models
from datetime import date, timedelta, datetime
from django.db.models import Sum, Count, Q, F, DecimalField, FloatField, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Coalesce
from django.utils.timezone import now
from rest_framework.views import APIView
from calendar import monthrange
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from accounts.models import UserProfile
from inventory.models import (
    SalesOrder, SalesOrderItem, Product, Category, 
    ProductBatch, PurchaseOrder, PurchaseOrderItem
)
from decimal import Decimal

from django.db.models import Sum, Count, Q, F, DecimalField, Value, Case, When, Min, Max

# 1. DAILY / WEEKLY / MONTHLY SALES REPORT

class SalesPeriodicReportAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get user's company
        try:
            profile = UserProfile.objects.select_related("company").get(user=request.user)
            company = profile.company
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Company not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        period = request.GET.get('period', 'daily')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        month_param = request.GET.get('month')  # YYYY-MM

        today = date.today()

        #  Month-based calendar filter (Bug_320 fix)
        if month_param:
            try:
                year, month = map(int, month_param.split('-'))
                from_date = f"{year}-{month:02d}-01"
                last_day = monthrange(year, month)[1]
                to_date = f"{year}-{month:02d}-{last_day}"
                period = 'monthly'
            except ValueError:
                return Response(
                    {"error": "Invalid month format. Expected YYYY-MM"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Default date range: last 30 days
            if not search_query:
                if not from_date:
                    from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
                if not to_date:
                    to_date = today.strftime('%Y-%m-%d')
            

        filters = Q(company=company)

        search_query = request.GET.get('search')

        # DATE FILTERS
        if from_date:
            filters &= Q(created_at__date__gte=from_date)

        if to_date:
            filters &= Q(created_at__date__lte=to_date)

        # SEARCH FILTER
        if search_query:
            filters &= (
                Q(customer_name__icontains=search_query) |
                Q(order_number__icontains=search_query) |
                Q(status__icontains=search_query)
            )
        else:
            # default report behavior
            filters &= Q(status='DELIVERED')

        orders = SalesOrder.objects.filter(filters)
        
        # Group by period
        if period == 'daily':
            sales_data = orders.annotate(
                period_date=TruncDay('created_at')
            ).values('period_date').annotate(
                total_orders=Count('id'),
                total_revenue=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField()),
                avg_order_value=Coalesce(
                    Sum('total_amount') / Count('id'),
                    Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ).order_by('period_date')

            for data in sales_data:
                day_orders = orders.filter(created_at__date=data['period_date'])
                items = SalesOrderItem.objects.filter(order__in=day_orders)
                data['total_items_sold'] = items.aggregate(total=Sum('quantity'))['total'] or 0
                data['period'] = data['period_date'].strftime('%Y-%m-%d')
                del data['period_date']

        elif period == 'weekly':
            sales_data = orders.annotate(
                week=TruncWeek('created_at')
            ).values('week').annotate(
                total_orders=Count('id'),
                total_revenue=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField()),
                avg_order_value=Coalesce(
                    Sum('total_amount') / Count('id'),
                    Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ).order_by('week')

            for data in sales_data:
                week_start = data['week']
                week_end = week_start + timedelta(days=6)
                week_orders = orders.filter(
                    created_at__date__gte=from_date,
            created_at__date__lte=to_date
                )
                items = SalesOrderItem.objects.filter(order__in=week_orders)
                data['total_items_sold'] = items.aggregate(total=Sum('quantity'))['total'] or 0
                data['period'] = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
                del data['week']

        else:  # monthly
            sales_data = orders.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                total_orders=Count('id'),
                total_revenue=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField()),
                avg_order_value=Coalesce(
                    Sum('total_amount') / Count('id'),
                    Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ).order_by('month')

            for data in sales_data:
                month_orders = orders.filter(
                    created_at__year=data['month'].year,
                    created_at__month=data['month'].month
                )
                items = SalesOrderItem.objects.filter(order__in=month_orders)
                data['total_items_sold'] = items.aggregate(total=Sum('quantity'))['total'] or 0
                data['period'] = data['month'].strftime('%B %Y')
                del data['month']

        # Calculate correct average daily sales
        days_count = (date.fromisoformat(to_date) - date.fromisoformat(from_date)).days + 1

        summary = {
            'total_revenue': float(orders.aggregate(total=Sum('total_amount'))['total'] or 0),
            'total_orders': orders.count(),
            'total_items_sold': SalesOrderItem.objects.filter(order__in=orders).aggregate(
                total=Sum('quantity')
            )['total'] or 0,
            'avg_daily_sales': (
                float(orders.aggregate(total=Sum('total_amount'))['total'] or 0) / days_count
                if days_count > 0 else 0
            ),
            'date_range': f"{from_date} to {to_date}"
        }

        return Response({
            'status': 'success',
            'company': company.name,
            'period': period,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': summary,
            'sales_data': sales_data
        }, status=status.HTTP_200_OK)



# 2. PRODUCT-WISE SALES REPORT

class ProductWiseSalesReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/product-wise/
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - category_id: Filter by category
        - sort_by: 'revenue', 'quantity', 'orders' (default: revenue)
        - limit: Number of products to return (default: 50)
        - company_id: Admin only
    
    Returns:
        - Sales breakdown by product
        - Quantity sold, revenue, margin
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        category_id = request.GET.get('category_id')
        sort_by = request.GET.get('sort_by', 'revenue')
        limit = int(request.GET.get('limit', 50))
        
        today = date.today()
        
        if not from_date:
            from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')

        # Get completed orders in date range
        orders = SalesOrder.objects.filter(
            company=company,
            status='DELIVERED',
            created_at__date__gte=from_date,
            created_at__date__lte=to_date
        )

        # Get order items with product details
        items = SalesOrderItem.objects.filter(
            order__in=orders
        ).select_related('product', 'product__category')

        if category_id:
            items = items.filter(product__category_id=category_id)

        # Aggregate by product
        product_sales = items.values(
            'product__id', 'product__name', 'product__sku', 
            'product__category__name', 'product__purchase_price', 'product__selling_price'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Value(0)),
            total_revenue=Coalesce(Sum(F('quantity') * F('price')), Value(0), output_field=DecimalField()),
            total_orders=Count('order', distinct=True),
            avg_selling_price=Coalesce(
                Sum(F('quantity') * F('price')) / Sum('quantity'),
                Value(0), output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

        # Calculate margin and profit
        result = []
        total_revenue_all = 0
        total_profit_all = 0

        for p in product_sales:
            purchase_price = float(p['product__purchase_price'] or 0)
            selling_price = float(p['product__selling_price'] or 0)
            
            # Use actual selling price from order if available
            avg_selling = float(p['avg_selling_price'] or selling_price)
            
            profit_per_unit = avg_selling - purchase_price
            total_profit = profit_per_unit * float(p['total_quantity'])
            margin_percentage = (profit_per_unit / avg_selling * 100) if avg_selling > 0 else 0
            
            product_data = {
                'product_id': p['product__id'],
                'product_name': p['product__name'],
                'sku': p['product__sku'],
                'category': p['product__category__name'] or 'Uncategorized',
                'total_quantity_sold': p['total_quantity'],
                'total_revenue': round(float(p['total_revenue']), 2),
                'total_orders': p['total_orders'],
                'avg_selling_price': round(avg_selling, 2),
                'purchase_price': round(purchase_price, 2),
                'profit_per_unit': round(profit_per_unit, 2),
                'total_profit': round(total_profit, 2),
                'margin_percentage': round(margin_percentage, 2)
            }
            
            total_revenue_all += float(p['total_revenue'])
            total_profit_all += total_profit
            result.append(product_data)

        # Sort results
        if sort_by == 'quantity':
            result.sort(key=lambda x: x['total_quantity_sold'], reverse=True)
        elif sort_by == 'orders':
            result.sort(key=lambda x: x['total_orders'], reverse=True)
        else:  # revenue
            result.sort(key=lambda x: x['total_revenue'], reverse=True)

        # Apply limit
        result = result[:limit]

        # Top products summary
        top_by_revenue = result[:5] if result else []
        top_by_quantity = sorted(result, key=lambda x: x['total_quantity_sold'], reverse=True)[:5] if result else []

        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': {
                'total_products_sold': len(result),
                'total_revenue': round(total_revenue_all, 2),
                'total_profit': round(total_profit_all, 2),
                'overall_margin': round((total_profit_all / total_revenue_all * 100), 2) if total_revenue_all > 0 else 0,
                'total_quantity_sold': sum(p['total_quantity_sold'] for p in result)
            },
            'top_products_by_revenue': top_by_revenue,
            'top_products_by_quantity': top_by_quantity,
            'product_sales': result
        }, status=status.HTTP_200_OK)



# 3. CATEGORY-WISE SALES REPORT

class CategoryWiseSalesReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/category-wise/
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - company_id: Admin only
    
    Returns:
        - Sales breakdown by category
        - Revenue, quantity, percentage contribution
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        today = date.today()
        
        if not from_date:
            from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')

        # Get completed orders
        orders = SalesOrder.objects.filter(
            company=company,
            status='DELIVERED',
            created_at__date__gte=from_date,
            created_at__date__lte=to_date
        )

        # Get order items with category
        items = SalesOrderItem.objects.filter(
            order__in=orders
        ).select_related('product__category')

        # Aggregate by category
        category_sales = items.values(
            'product__category__id', 'product__category__name'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Value(0), output_field=models.IntegerField()),
            total_revenue=Coalesce(
                Sum(F('quantity') * F('price')), 
                Value(0), 
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            total_orders=Count('order', distinct=True),
            unique_products=Count('product', distinct=True)
        ).order_by('-total_revenue')

        # Calculate total revenue for percentages - convert to float for division
        total_revenue_all = float(items.aggregate(
            total=Sum(F('quantity') * F('price'))
        )['total'] or 0)

        result = []
        for cat in category_sales:
            revenue = float(cat['total_revenue'] or 0)
            percentage = (revenue / total_revenue_all * 100) if total_revenue_all > 0 else 0
            orders_count = cat['total_orders'] or 0
            
            result.append({
                'category_id': cat['product__category__id'],
                'category_name': cat['product__category__name'] or 'Uncategorized',
                'total_quantity_sold': cat['total_quantity'] or 0,
                'total_revenue': round(revenue, 2),
                'total_orders': orders_count,
                'unique_products': cat['unique_products'] or 0,
                'contribution_percentage': round(percentage, 2),
                'avg_order_value': round(revenue / orders_count, 2) if orders_count > 0 else 0
            })

        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': {
                'total_categories': len(result),
                'total_revenue': round(total_revenue_all, 2),
                'total_quantity_sold': items.aggregate(total=Sum('quantity'))['total'] or 0,
                'top_category': result[0]['category_name'] if result else 'N/A'
            },
            'category_sales': result
        }, status=status.HTTP_200_OK)


# 4. BATCH-WISE SALES REPORT

class BatchWiseSalesReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/batch-wise/
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - product_id: Filter by product
        - company_id: Admin only
    
    Returns:
        - Sales breakdown by batch number
        - FEFO compliance tracking
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        product_id = request.GET.get('product_id')
        
        today = date.today()
        
        if not from_date:
            from_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')  # Last 90 days
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')

        # Get stock transactions for sales (OUT, SALE)
        from inventory.models import StockTransaction
        
        transactions = StockTransaction.objects.filter(
            company=company,
            transaction_type='OUT',
            source='SALE',
            created_at__date__gte=from_date,
            created_at__date__lte=to_date,
            batch__isnull=False  # Only include transactions with batch
        ).select_related('product', 'batch')

        if product_id:
            transactions = transactions.filter(product_id=product_id)

        # Aggregate by batch
        batch_sales = transactions.values(
            'batch__id', 'batch__batch_number', 'batch__expiry_date',
            'product__id', 'product__name', 'product__sku'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Value(0), output_field=models.IntegerField()),
            total_transactions=Count('id'),
            first_sale_date=Min('created_at'),
            last_sale_date=Max('created_at')
        ).order_by('-total_quantity')

        result = []
        total_quantity_all = 0
        
        for batch in batch_sales:
            if not batch['batch__id']:
                continue  # Skip transactions without batch
                
            expiry_date = batch['batch__expiry_date']
            days_to_expiry = (expiry_date - today).days if expiry_date else None
            expiry_status = 'EXPIRED' if expiry_date and expiry_date < today else \
                           'NEAR_EXPIRY' if expiry_date and days_to_expiry and days_to_expiry <= 30 else \
                           'SAFE' if expiry_date else 'NO_EXPIRY'
            
            batch_data = {
                'batch_id': batch['batch__id'],
                'batch_number': batch['batch__batch_number'] or 'NO-BATCH',
                'product_id': batch['product__id'],
                'product_name': batch['product__name'],
                'product_sku': batch['product__sku'],
                'expiry_date': expiry_date.strftime('%Y-%m-%d') if expiry_date else None,
                'expiry_status': expiry_status,
                'days_to_expiry': days_to_expiry,
                'total_quantity_sold': batch['total_quantity'],
                'total_transactions': batch['total_transactions'],
                'first_sale_date': batch['first_sale_date'].strftime('%Y-%m-%d') if batch['first_sale_date'] else None,
                'last_sale_date': batch['last_sale_date'].strftime('%Y-%m-%d') if batch['last_sale_date'] else None
            }
            
            total_quantity_all += batch['total_quantity']
            result.append(batch_data)

        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': {
                'total_batches_sold': len(result),
                'total_quantity_sold': total_quantity_all,
                'batches_with_expiry': len([b for b in result if b['expiry_date']]),
                'expired_batches_sold': len([b for b in result if b['expiry_status'] == 'EXPIRED'])
            },
            'batch_sales': result[:100]  # Limit to 100 records
        }, status=status.HTTP_200_OK)


# 5. REFUND & RETURN REPORTS

class RefundReturnReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/refunds/
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - company_id: Admin only
    
    Returns:
        - Refunded/Cancelled orders report
        - Total refund amount
        - Reasons (if available)
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        
        today = date.today()
        
        if not from_date:
            from_date = (today - timedelta(days=90)).strftime('%Y-%m-%d')
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')

        # Get cancelled orders (refunds/returns)
        cancelled_orders = SalesOrder.objects.filter(
            company=company,
            status='CANCELLED',
            created_at__date__gte=from_date,
            created_at__date__lte=to_date
        ).order_by('-created_at')

        # Calculate totals
        total_refund_amount = cancelled_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0

        # Get items from cancelled orders
        cancelled_items = SalesOrderItem.objects.filter(
            order__in=cancelled_orders
        ).select_related('product')

        # Group by date
        refunds_by_day = cancelled_orders.annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            refund_count=Count('id'),
            refund_amount=Coalesce(Sum('total_amount'), Value(0), output_field=DecimalField())
        ).order_by('-day')

        # Detailed refund list
        refund_list = []
        for order in cancelled_orders[:100]:  # Limit to 100
            items = SalesOrderItem.objects.filter(order=order)
            refund_list.append({
                'order_id': order.id,
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'refund_date': order.created_at.date().strftime('%Y-%m-%d'),
                'refund_amount': float(order.total_amount),
                'items_count': items.count(),
                'items': [
                    {
                        'product_name': item.product.name,
                        'quantity': item.quantity,
                        'price': float(item.price),
                        'total': float(item.quantity * item.price)
                    }
                    for item in items
                ][:5]  # Limit to 5 items per order
            })

        # Refund rate
        total_orders = SalesOrder.objects.filter(
            company=company,
            created_at__date__gte=from_date,
            created_at__date__lte=to_date
        ).exclude(status='CANCELLED').count()

        refund_rate = (cancelled_orders.count() / (total_orders + cancelled_orders.count()) * 100) if (total_orders + cancelled_orders.count()) > 0 else 0

        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': {
                'total_refunds': cancelled_orders.count(),
                'total_refund_amount': round(float(total_refund_amount), 2),
                'total_items_returned': cancelled_items.aggregate(total=Sum('quantity'))['total'] or 0,
                'refund_rate': round(refund_rate, 2),
                'avg_refund_value': round(float(total_refund_amount) / cancelled_orders.count(), 2) if cancelled_orders.count() > 0 else 0
            },
            'refunds_by_day': [
                {
                    'date': item['day'].strftime('%Y-%m-%d'),
                    'refund_count': item['refund_count'],
                    'refund_amount': float(item['refund_amount'])
                }
                for item in refunds_by_day[:30]  # Last 30 days
            ],
            'recent_refunds': refund_list[:20]
        }, status=status.HTTP_200_OK)



# 6. MARGIN REPORT (Selling Price vs Purchase Price)

class MarginReportAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/margin/
    
    Query Parameters:
        - from_date: Start date
        - to_date: End date
        - category_id: Filter by category
        - product_id: Filter by product
        - company_id: Admin only
    
    Returns:
        - Profit margin analysis
        - Gross profit, margin percentage
        - Loss-making products
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Get parameters
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        
        today = date.today()
        
        if not from_date:
            from_date = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        if not to_date:
            to_date = today.strftime('%Y-%m-%d')

        # Get completed orders
        orders = SalesOrder.objects.filter(
            company=company,
            status='DELIVERED',
            created_at__date__gte=from_date,
            created_at__date__lte=to_date
        )

        # Get order items with product purchase price
        items = SalesOrderItem.objects.filter(
            order__in=orders
        ).select_related('product', 'product__category')

        if category_id:
            items = items.filter(product__category_id=category_id)
        if product_id:
            items = items.filter(product_id=product_id)

        # Calculate margin by product
        product_margins = items.values(
            'product__id', 'product__name', 'product__sku',
            'product__category__name', 'product__purchase_price'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Value(0), output_field=models.IntegerField()),
            total_revenue=Coalesce(
                Sum(F('quantity') * F('price')), 
                Value(0), 
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            avg_selling_price=Case(
                When(
                    total_quantity__gt=0,
                    then=Sum(F('quantity') * F('price')) / Sum('quantity')
                ),
                default=Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )

        margin_data = []
        total_revenue_all = 0
        total_cost_all = 0
        total_profit_all = 0
        loss_making_products = 0

        for p in product_margins:
            purchase_price = float(p['product__purchase_price'] or 0)
            avg_selling = float(p['avg_selling_price'] or 0)
            quantity = float(p['total_quantity'] or 0)
            revenue = float(p['total_revenue'] or 0)
            
            # Calculate costs and profit
            cost_of_goods = purchase_price * quantity
            gross_profit = revenue - cost_of_goods
            margin_percentage = (gross_profit / revenue * 100) if revenue > 0 else 0
            
            if gross_profit < 0:
                loss_making_products += 1
            
            margin_data.append({
                'product_id': p['product__id'],
                'product_name': p['product__name'],
                'sku': p['product__sku'],
                'category': p['product__category__name'] or 'Uncategorized',
                'quantity_sold': quantity,
                'revenue': round(revenue, 2),
                'cost_of_goods': round(cost_of_goods, 2),
                'gross_profit': round(gross_profit, 2),
                'margin_percentage': round(margin_percentage, 2),
                'purchase_price': round(purchase_price, 2),
                'avg_selling_price': round(avg_selling, 2)
            })
            
            total_revenue_all += revenue
            total_cost_all += cost_of_goods
            total_profit_all += gross_profit

        # Overall margin
        overall_margin = (total_profit_all / total_revenue_all * 100) if total_revenue_all > 0 else 0

        # Margin by category
        category_margins = items.values(
            'product__category__id', 'product__category__name'
        ).annotate(
            total_revenue=Coalesce(
                Sum(F('quantity') * F('price')), 
                Value(0), 
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            total_cost=Coalesce(
                Sum(F('quantity') * F('product__purchase_price')),
                Value(0), 
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        margin_by_category = []
        for cat in category_margins:
            revenue = float(cat['total_revenue'] or 0)
            cost = float(cat['total_cost'] or 0)
            profit = revenue - cost
            margin = (profit / revenue * 100) if revenue > 0 else 0
            
            margin_by_category.append({
                'category_id': cat['product__category__id'],
                'category_name': cat['product__category__name'] or 'Uncategorized',
                'revenue': round(revenue, 2),
                'cost': round(cost, 2),
                'profit': round(profit, 2),
                'margin_percentage': round(margin, 2)
            })

        # Sort by margin
        margin_data.sort(key=lambda x: x['margin_percentage'], reverse=True)
        
        # High margin (>30%) and low margin (<10%) products
        high_margin_products = [p for p in margin_data if p['margin_percentage'] > 30][:10]
        low_margin_products = [p for p in margin_data if 0 < p['margin_percentage'] < 10][:10]
        loss_products = [p for p in margin_data if p['gross_profit'] < 0][:10]

        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date,
                'to': to_date
            },
            'summary': {
                'total_revenue': round(total_revenue_all, 2),
                'total_cost_of_goods': round(total_cost_all, 2),
                'total_gross_profit': round(total_profit_all, 2),
                'overall_margin_percentage': round(overall_margin, 2),
                'products_sold': len(margin_data),
                'loss_making_products': loss_making_products,
                'profitable_products': len(margin_data) - loss_making_products
            },
            'margin_by_category': margin_by_category,
            'high_margin_products': high_margin_products,
            'low_margin_products': low_margin_products,
            'loss_making_products': loss_products,
            'product_margins': margin_data[:50]  # Limit to 50 products
        }, status=status.HTTP_200_OK)



# 7. SALES DASHBOARD SUMMARY

class SalesDashboardSummaryAPIView(APIView):
    """
    API: GET /inventory/api/reports/sales/dashboard/
    
    Quick sales summary for dashboard
    
    Returns:
        - Today's sales
        - This week's sales
        - This month's sales
        - Comparison with previous periods
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
        except Exception:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        # Last period for comparison
        yesterday = today - timedelta(days=1)
        last_week_start = week_start - timedelta(days=7)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)

        # Helper function to get sales data
        def get_sales_data(start_date, end_date):
            orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            )
            
            revenue = orders.aggregate(total=Sum('total_amount'))['total'] or 0
            order_count = orders.count()
            
            items = SalesOrderItem.objects.filter(order__in=orders)
            quantity = items.aggregate(total=Sum('quantity'))['total'] or 0
            
            return {
                'revenue': float(revenue),
                'orders': order_count,
                'quantity': quantity
            }

        # Current period data
        today_data = get_sales_data(today, today)
        week_data = get_sales_data(week_start, today)
        month_data = get_sales_data(month_start, today)

        # Previous period data for comparison
        yesterday_data = get_sales_data(yesterday, yesterday)
        last_week_data = get_sales_data(last_week_start, week_start - timedelta(days=1))
        last_month_data = get_sales_data(last_month_start, month_start - timedelta(days=1))

        # Calculate growth percentages
        today_growth = (
            ((today_data['revenue'] - yesterday_data['revenue']) / yesterday_data['revenue'] * 100)
            if yesterday_data['revenue'] > 0 else 100
        )
        
        week_growth = (
            ((week_data['revenue'] - last_week_data['revenue']) / last_week_data['revenue'] * 100)
            if last_week_data['revenue'] > 0 else 100
        )
        
        month_growth = (
            ((month_data['revenue'] - last_month_data['revenue']) / last_month_data['revenue'] * 100)
            if last_month_data['revenue'] > 0 else 100
        )

        return Response({
            'status': 'success',
            'company': company.name,
            'date': today.strftime('%Y-%m-%d'),
            'today': {
                'revenue': round(today_data['revenue'], 2),
                'orders': today_data['orders'],
                'quantity': today_data['quantity'],
                'growth_percentage': round(today_growth, 2)
            },
            'this_week': {
                'revenue': round(week_data['revenue'], 2),
                'orders': week_data['orders'],
                'quantity': week_data['quantity'],
                'growth_percentage': round(week_growth, 2)
            },
            'this_month': {
                'revenue': round(month_data['revenue'], 2),
                'orders': month_data['orders'],
                'quantity': month_data['quantity'],
                'growth_percentage': round(month_growth, 2)
            }
        }, status=status.HTTP_200_OK)