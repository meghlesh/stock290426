from datetime import date, timedelta, datetime
from django.db import models
from django.db.models import (
    Sum, Count, Q, F, DecimalField, Value, Case, When, Min, Max, Avg
)
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, Coalesce
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, BasePermission
from decimal import Decimal

from accounts.models import UserProfile
from inventory.models import (
    Product, Category, ProductBatch, SalesOrder, SalesOrderItem,
    StockTransaction, InventoryAlert, PurchaseOrder
)
from company.models import Company



# ROLE-BASED PERMISSION CLASSES


class IsAdminUser(BasePermission):
    """Permission for Admin users (superuser)"""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superuser


class IsCompanyOwner(BasePermission):
    """Permission for Company Owners"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role == 'COMPANY_OWNER'
        except UserProfile.DoesNotExist:
            return False


class IsStoreManager(BasePermission):
    """
    Permission for Store Managers
    Can view all inventory and sales data, but cannot modify certain settings
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        # You can define store manager role in UserProfile
        # For now, we'll treat COMPANY_OWNER as Store Manager
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role in ['COMPANY_OWNER', 'STORE_MANAGER']
        except UserProfile.DoesNotExist:
            return False


class IsInventoryManager(BasePermission):
    """
    Permission for Inventory Managers
    Can view and manage inventory, but not financial data
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role in ['COMPANY_OWNER', 'INVENTORY_MANAGER']
        except UserProfile.DoesNotExist:
            return False


class IsAuditor(BasePermission):
    """
    Permission for Auditors
    Read-only access to all data, no modifications
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            profile = UserProfile.objects.get(user=request.user)
            return profile.role in ['COMPANY_OWNER', 'AUDITOR']
        except UserProfile.DoesNotExist:
            return False



# HELPER FUNCTIONS


def get_user_company(request):
    """Get company based on user role and permissions"""
    try:
        # Superuser can access any company via company_id parameter
        if request.user.is_superuser and request.GET.get('company_id'):
            return Company.objects.get(id=request.GET.get('company_id'))
        
        # Regular users get their own company
        profile = UserProfile.objects.select_related("company").get(user=request.user)
        return profile.company
    except Exception:
        return None


def get_user_role(request):
    """Get current user's role for dashboard customization"""
    if request.user.is_superuser:
        return 'ADMIN'
    try:
        profile = UserProfile.objects.get(user=request.user)
        return profile.role
    except UserProfile.DoesNotExist:
        return 'UNKNOWN'


def filter_by_user_role(queryset, request, field_name='company'):
    """Apply role-based filtering to querysets"""
    company = get_user_company(request)
    if company:
        filter_kwargs = {field_name: company}
        return queryset.filter(**filter_kwargs)
    return queryset.none()



# 1. KEY KPIs DASHBOARD API

class DashboardKPIsAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/kpis/
    
    Returns all key KPIs for dashboard:
        - Total stock value (purchase price)
        - Total stock value (selling price)
        - Low stock count
        - Near-expiry items count
        - Expired stock value
        - Total products
        - Total sales (today/week/month)
        - Total purchase orders
    
    Role-based access:
        - Admin: All data + multi-company
        - Store Manager: All KPIs
        - Inventory Manager: Inventory KPIs only
        - Auditor: Read-only all KPIs
    """
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Apply role-based permissions"""
        user_role = get_user_role(self.request)
        if user_role == 'ADMIN':
            self.permission_classes = [IsAuthenticated]
        elif user_role == 'COMPANY_OWNER':
            self.permission_classes = [IsCompanyOwner]
        elif user_role == 'INVENTORY_MANAGER':
            self.permission_classes = [IsInventoryManager]
        elif user_role == 'AUDITOR':
            self.permission_classes = [IsAuditor]
        else:
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()

    def get(self, request):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        user_role = get_user_role(request)
        
        
        # Get all active products
        products = Product.objects.filter(company=company)
        total_products = products.count()
        
        # Get all active batches with stock
        active_batches = ProductBatch.objects.filter(
            company=company,
            quantity__gt=0,
            is_active=True
        ).select_related('product')
        
        # Total stock value (purchase price)
        total_stock_value_purchase = 0
        total_stock_value_selling = 0
        total_stock_quantity = 0
        
        for batch in active_batches:
            if batch.product:
                purchase_price = float(batch.product.purchase_price or 0)
                selling_price = float(batch.product.selling_price or 0)
                total_stock_value_purchase += batch.quantity * purchase_price
                total_stock_value_selling += batch.quantity * selling_price
                total_stock_quantity += batch.quantity
        
        # Low stock count (products with stock <= low_stock_limit)
        low_stock_count = 0
        for product in products:
            # Calculate sellable stock from non-expired batches
            sellable_stock = ProductBatch.objects.filter(
                company=company,
                product=product,
                expiry_date__gte=today,
                quantity__gt=0,
                is_active=True
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if sellable_stock <= product.low_stock_limit:
                low_stock_count += 1
        
        # Near-expiry items (expiring in next 30 days)
        near_expiry_limit = today + timedelta(days=30)
        near_expiry_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__gte=today,
            expiry_date__lte=near_expiry_limit,
            quantity__gt=0,
            is_active=True
        )
        near_expiry_count = near_expiry_batches.count()
        near_expiry_quantity = near_expiry_batches.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Expired stock value
        expired_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0,
            is_active=True
        )
        expired_count = expired_batches.count()
        expired_quantity = expired_batches.aggregate(total=Sum('quantity'))['total'] or 0
        
        expired_stock_value = 0
        for batch in expired_batches:
            if batch.product:
                expired_stock_value += batch.quantity * float(batch.product.purchase_price or 0)
        
        sales_kpis = {}
        
        if user_role in ['ADMIN', 'COMPANY_OWNER', 'STORE_MANAGER', 'AUDITOR']:
            # Today's sales
            today_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date=today
            )
            today_sales = today_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            today_orders_count = today_orders.count()
            
            # This week's sales
            week_start = today - timedelta(days=today.weekday())
            week_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date__gte=week_start,
                created_at__date__lte=today
            )
            week_sales = week_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            
            # This month's sales
            month_start = today.replace(day=1)
            month_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date__gte=month_start,
                created_at__date__lte=today
            )
            month_sales = month_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            
            sales_kpis = {
                'today_sales': round(float(today_sales), 2),
                'today_orders': today_orders_count,
                'week_sales': round(float(week_sales), 2),
                'month_sales': round(float(month_sales), 2),
            }
        
        pending_po_count = PurchaseOrder.objects.filter(
            company=company,
            status='ORDERED'
        ).count()
        
        draft_po_count = PurchaseOrder.objects.filter(
            company=company,
            status='DRAFT'
        ).count()
        
        unread_alerts = InventoryAlert.objects.filter(
            company=company,
            is_read=False
        ).count()
        
        # Build response based on user role
        response_data = {
            'status': 'success',
            'company': company.name,
            'user_role': user_role,
            'report_date': today.strftime('%Y-%m-%d'),
            'inventory_kpis': {
                'total_products': total_products,
                'total_stock_quantity': total_stock_quantity,
                'total_stock_value_purchase': round(total_stock_value_purchase, 2),
                'total_stock_value_selling': round(total_stock_value_selling, 2),
                'potential_profit': round(total_stock_value_selling - total_stock_value_purchase, 2),
                'low_stock_count': low_stock_count,
                'near_expiry': {
                    'batch_count': near_expiry_count,
                    'total_quantity': near_expiry_quantity
                },
                'expired_stock': {
                    'batch_count': expired_count,
                    'total_quantity': expired_quantity,
                    'total_value': round(expired_stock_value, 2)
                }
            },
            'purchase_kpis': {
                'pending_po_count': pending_po_count,
                'draft_po_count': draft_po_count
            },
            'alerts': {
                'unread_count': unread_alerts
            }
        }
        
        # Add sales KPIs only if user has permission
        if sales_kpis:
            response_data['sales_kpis'] = sales_kpis
        
        return Response(response_data, status=status.HTTP_200_OK)



# 2. SALES TRENDS CHART API


class SalesTrendsChartAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/charts/sales-trends/
    
    Returns sales trend data for charts
    Query Parameters:
        - period: 'daily', 'weekly', 'monthly' (default: daily)
        - days: Number of days (default: 30)
        - company_id: Admin only
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        user_role = get_user_role(request)
        
        # Restrict access for Inventory Managers
        if user_role == 'INVENTORY_MANAGER':
            return Response({
                'status': 'success',
                'message': 'Sales trends not available for Inventory Managers',
                'chart_data': {
                    'labels': [],
                    'datasets': []
                }
            })
        
        period = request.GET.get('period', 'daily')
        days = int(request.GET.get('days', 30))
        
        today = date.today()
        from_date = today - timedelta(days=days)
        
        # Get all orders in date range
        orders = SalesOrder.objects.filter(
            company=company,
            status='DELIVERED',
            created_at__date__gte=from_date,
            created_at__date__lte=today
        ).order_by('created_at')
        
        # Get all order items for these orders
        order_ids = orders.values_list('id', flat=True)
        order_items = SalesOrderItem.objects.filter(
            order_id__in=list(order_ids)
        ).select_related('order')
        
        # Create a dictionary to store order totals and item counts
        order_data = {}
        for order in orders:
            order_data[order.id] = {
                'date': order.created_at.date(),
                'revenue': float(order.total_amount or 0),
                'items_sold': 0
            }
        
        # Add item counts
        for item in order_items:
            if item.order_id in order_data:
                order_data[item.order_id]['items_sold'] += item.quantity or 0
        
        # Group by period
        if period == 'daily':
            # Group by date
            daily_data = {}
            for order_id, data in order_data.items():
                date_key = data['date']
                if date_key not in daily_data:
                    daily_data[date_key] = {
                        'revenue': 0,
                        'orders_count': 0,
                        'items_sold': 0
                    }
                daily_data[date_key]['revenue'] += data['revenue']
                daily_data[date_key]['orders_count'] += 1
                daily_data[date_key]['items_sold'] += data['items_sold']
            
            # Sort by date
            sorted_dates = sorted(daily_data.keys())
            
            labels = []
            revenue_data = []
            orders_data = []
            items_data = []
            
            for date_key in sorted_dates:
                labels.append(date_key.strftime('%d %b'))
                revenue_data.append(round(daily_data[date_key]['revenue'], 2))
                orders_data.append(daily_data[date_key]['orders_count'])
                items_data.append(daily_data[date_key]['items_sold'])
        
        elif period == 'weekly':
            # Group by week
            weekly_data = {}
            for order_id, data in order_data.items():
                # Get week start (Monday)
                week_start = data['date'] - timedelta(days=data['date'].weekday())
                week_key = week_start.strftime('%Y-%W')
                
                if week_key not in weekly_data:
                    weekly_data[week_key] = {
                        'week_start': week_start,
                        'week_end': week_start + timedelta(days=6),
                        'revenue': 0,
                        'orders_count': 0,
                        'items_sold': 0
                    }
                weekly_data[week_key]['revenue'] += data['revenue']
                weekly_data[week_key]['orders_count'] += 1
                weekly_data[week_key]['items_sold'] += data['items_sold']
            
            # Sort by week
            sorted_weeks = sorted(weekly_data.keys())
            
            labels = []
            revenue_data = []
            orders_data = []
            items_data = []
            
            for week_key in sorted_weeks:
                week = weekly_data[week_key]
                labels.append(f"{week['week_start'].strftime('%d %b')} - {week['week_end'].strftime('%d %b')}")
                revenue_data.append(round(week['revenue'], 2))
                orders_data.append(week['orders_count'])
                items_data.append(week['items_sold'])
        
        else:  # monthly
            # Group by month
            monthly_data = {}
            for order_id, data in order_data.items():
                month_key = data['date'].strftime('%Y-%m')
                
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'month': data['date'].strftime('%B %Y'),
                        'revenue': 0,
                        'orders_count': 0,
                        'items_sold': 0
                    }
                monthly_data[month_key]['revenue'] += data['revenue']
                monthly_data[month_key]['orders_count'] += 1
                monthly_data[month_key]['items_sold'] += data['items_sold']
            
            # Sort by month
            sorted_months = sorted(monthly_data.keys())
            
            labels = []
            revenue_data = []
            orders_data = []
            items_data = []
            
            for month_key in sorted_months:
                labels.append(monthly_data[month_key]['month'])
                revenue_data.append(round(monthly_data[month_key]['revenue'], 2))
                orders_data.append(monthly_data[month_key]['orders_count'])
                items_data.append(monthly_data[month_key]['items_sold'])
        
        # Calculate summary
        total_revenue = sum(revenue_data)
        total_orders = sum(orders_data)
        total_items = sum(items_data)
        avg_revenue = total_revenue / len(revenue_data) if revenue_data else 0
        
        return Response({
            'status': 'success',
            'company': company.name,
            'period': period,
            'date_range': {
                'from': from_date.strftime('%Y-%m-%d'),
                'to': today.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_revenue': round(total_revenue, 2),
                'total_orders': total_orders,
                'avg_daily_revenue': round(avg_revenue, 2),
                'total_items_sold': total_items
            },
            'chart_data': {
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Revenue (₹)',
                        'data': revenue_data,
                        'borderColor': '#3b82f6',
                        'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                        'yAxisID': 'y'
                    },
                    {
                        'label': 'Orders',
                        'data': orders_data,
                        'borderColor': '#10b981',
                        'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                        'yAxisID': 'y1'
                    }
                ]
            },
            'table_data': {
                'labels': labels,
                'revenue': revenue_data,
                'orders': orders_data,
                'items': items_data
            }
        }, status=status.HTTP_200_OK)



# 3. STOCK MOVEMENT TRENDS CHART API

class StockMovementTrendsChartAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/charts/stock-movement/
    
    Returns stock movement trends (IN/OUT) for charts
    Query Parameters:
        - days: Number of days (default: 30)
        - company_id: Admin only
    
    Role-based access:
        - Admin: All data
        - Store Manager: Full access
        - Inventory Manager: Full access
        - Auditor: Read-only
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        days = int(request.GET.get('days', 30))
        today = date.today()
        from_date = today - timedelta(days=days)
        
        # Get stock transactions
        transactions = StockTransaction.objects.filter(
            company=company,
            created_at__date__gte=from_date,
            created_at__date__lte=today
        )
        
        # Daily stock movement
        daily_movement = transactions.annotate(
            day=TruncDay('created_at')
        ).values('day').annotate(
            stock_in=Coalesce(
                Sum('quantity', filter=Q(transaction_type='IN')),
                Value(0),
                output_field=models.IntegerField()
            ),
            stock_out=Coalesce(
                Sum('quantity', filter=Q(transaction_type='OUT')),
                Value(0),
                output_field=models.IntegerField()
            ),
            adjustment=Coalesce(
                Sum('quantity', filter=Q(source='MANUAL')),
                Value(0),
                output_field=models.IntegerField()
            )
        ).order_by('day')
        
        labels = []
        stock_in_data = []
        stock_out_data = []
        net_movement_data = []
        
        for item in daily_movement:
            labels.append(item['day'].strftime('%d %b'))
            stock_in_data.append(item['stock_in'])
            stock_out_data.append(item['stock_out'])
            net_movement = item['stock_in'] - item['stock_out']
            net_movement_data.append(net_movement)
        
        # Summary statistics
        total_in = sum(stock_in_data)
        total_out = sum(stock_out_data)
        
        return Response({
            'status': 'success',
            'company': company.name,
            'date_range': {
                'from': from_date.strftime('%Y-%m-%d'),
                'to': today.strftime('%Y-%m-%d')
            },
            'summary': {
                'total_stock_in': total_in,
                'total_stock_out': total_out,
                'net_movement': total_in - total_out,
                'avg_daily_in': round(total_in / days, 2),
                'avg_daily_out': round(total_out / days, 2)
            },
            'chart_data': {
                'labels': labels,
                'datasets': [
                    {
                        'label': 'Stock In',
                        'data': stock_in_data,
                        'borderColor': '#10b981',
                        'backgroundColor': 'rgba(16, 185, 129, 0.1)'
                    },
                    {
                        'label': 'Stock Out',
                        'data': stock_out_data,
                        'borderColor': '#ef4444',
                        'backgroundColor': 'rgba(239, 68, 68, 0.1)'
                    },
                    {
                        'label': 'Net Movement',
                        'data': net_movement_data,
                        'borderColor': '#8b5cf6',
                        'backgroundColor': 'rgba(139, 92, 246, 0.1)',
                        'borderDash': [5, 5]
                    }
                ]
            }
        }, status=status.HTTP_200_OK)



# 4. CATEGORY CONTRIBUTION CHART API

class CategoryContributionChartAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/charts/category-contribution/
    
    Returns category-wise contribution to sales and stock
    Query Parameters:
        - type: 'sales', 'stock', 'both' (default: both)
        - limit: Number of categories (default: 10)
        - company_id: Admin only
    
    Role-based access:
        - Admin: All data
        - Store Manager: Full access
        - Inventory Manager: Stock data only
        - Auditor: Read-only
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        user_role = get_user_role(request)
        chart_type = request.GET.get('type', 'both')
        limit = int(request.GET.get('limit', 10))
        
        today = date.today()
        
        # Get all categories for this company
        categories = Category.objects.filter(company=company)
        
        category_data = []
        
        for category in categories:
            category_info = {
                'category_id': category.id,
                'category_name': category.name
            }
            
            # Stock value by category (available to all roles)
            products = Product.objects.filter(company=company, category=category)
            stock_value = 0
            stock_quantity = 0
            
            for product in products:
                batches = ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=today,
                    quantity__gt=0,
                    is_active=True
                )
                product_stock = batches.aggregate(total=Sum('quantity'))['total'] or 0
                stock_quantity += product_stock
                stock_value += product_stock * float(product.purchase_price or 0)
            
            category_info['stock_quantity'] = stock_quantity
            category_info['stock_value'] = round(stock_value, 2)
            
            # Sales data (restricted for Inventory Managers)
            if user_role != 'INVENTORY_MANAGER' and chart_type in ['sales', 'both']:
                # Sales in last 30 days
                from_date = today - timedelta(days=30)
                orders = SalesOrder.objects.filter(
                    company=company,
                    status='DELIVERED',
                    created_at__date__gte=from_date
                )
                
                items = SalesOrderItem.objects.filter(
                    order__in=orders,
                    product__category=category
                )
                
                sales_revenue = items.aggregate(
                    total=Sum(F('quantity') * F('price'))
                )['total'] or 0
                sales_quantity = items.aggregate(total=Sum('quantity'))['total'] or 0
                
                category_info['sales_revenue'] = round(float(sales_revenue), 2)
                category_info['sales_quantity'] = sales_quantity
            
            category_data.append(category_info)
        
        # Sort by stock value
        category_data.sort(key=lambda x: x['stock_value'], reverse=True)
        category_data = category_data[:limit]
        
        # Prepare chart data
        labels = [c['category_name'] for c in category_data]
        
        response_data = {
            'status': 'success',
            'company': company.name,
            'chart_type': chart_type,
            'total_categories': len(categories),
            'categories': category_data,
            'chart_data': {
                'labels': labels,
                'datasets': []
            }
        }
        
        # Add stock value dataset
        if chart_type in ['stock', 'both']:
            response_data['chart_data']['datasets'].append({
                'label': 'Stock Value',
                'data': [c['stock_value'] for c in category_data],
                'backgroundColor': [
                    '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                    '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#6b7280'
                ]
            })
        
        # Add sales revenue dataset
        if chart_type in ['sales', 'both'] and user_role != 'INVENTORY_MANAGER':
            response_data['chart_data']['datasets'].append({
                'label': 'Sales Revenue (30 days)',
                'data': [c.get('sales_revenue', 0) for c in category_data],
                'backgroundColor': [
                    '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6',
                    '#f97316', '#6366f1', '#6b7280', '#3b82f6', '#10b981'
                ]
            })
        
        return Response(response_data, status=status.HTTP_200_OK)



# 5. ROLE-BASED DASHBOARD API

class RoleBasedDashboardAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/
    
    Returns complete dashboard data based on user role
    This is a single endpoint that returns all relevant data
    for the user's role
    
    Query Parameters:
        - company_id: Admin only - view other companies
    
    Role-specific views:
        - Admin: All data + company selector
        - Store Manager: Sales + Inventory KPIs
        - Inventory Manager: Inventory KPIs only
        - Auditor: Read-only all data
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        user_role = get_user_role(request)
        today = date.today()
        
        # Base dashboard data
        dashboard_data = {
            'status': 'success',
            'company': {
                'id': company.id,
                'name': company.name,
                'email': company.email
            },
            'user': {
                'username': request.user.username,
                'role': user_role,
                'is_superuser': request.user.is_superuser
            },
            'report_date': today.strftime('%Y-%m-%d'),
            'report_time': now().strftime('%H:%M:%S'),
            'modules': {}
        }
        
        products = Product.objects.filter(company=company)
        active_batches = ProductBatch.objects.filter(
            company=company,
            quantity__gt=0,
            is_active=True
        )
        
        # Stock value calculation
        stock_value_purchase = 0
        stock_value_selling = 0
        
        for batch in active_batches.select_related('product'):
            if batch.product:
                purchase_price = float(batch.product.purchase_price or 0)
                selling_price = float(batch.product.selling_price or 0)
                stock_value_purchase += batch.quantity * purchase_price
                stock_value_selling += batch.quantity * selling_price
        
        # Low stock count
        low_stock_count = 0
        near_expiry_limit = today + timedelta(days=30)
        
        for product in products:
            sellable_stock = ProductBatch.objects.filter(
                company=company,
                product=product,
                expiry_date__gte=today,
                quantity__gt=0,
                is_active=True
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            if sellable_stock <= product.low_stock_limit:
                low_stock_count += 1
        
        # Near expiry and expired
        near_expiry_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__gte=today,
            expiry_date__lte=near_expiry_limit,
            quantity__gt=0,
            is_active=True
        )
        
        expired_batches = ProductBatch.objects.filter(
            company=company,
            expiry_date__lt=today,
            quantity__gt=0,
            is_active=True
        )
        
        expired_value = 0
        for batch in expired_batches.select_related('product'):
            if batch.product:
                expired_value += batch.quantity * float(batch.product.purchase_price or 0)
        
        dashboard_data['modules']['inventory_summary'] = {
            'total_products': products.count(),
            'total_batches': active_batches.count(),
            'total_stock_quantity': active_batches.aggregate(total=Sum('quantity'))['total'] or 0,
            'total_stock_value': round(stock_value_purchase, 2),
            'total_selling_value': round(stock_value_selling, 2),
            'low_stock_count': low_stock_count,
            'near_expiry_count': near_expiry_batches.count(),
            'expired_batches_count': expired_batches.count(),
            'expired_stock_value': round(expired_value, 2)
        }
        
        if user_role in ['ADMIN', 'COMPANY_OWNER', 'STORE_MANAGER', 'AUDITOR']:
            # Today's sales
            today_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date=today
            )
            
            # This month's sales
            month_start = today.replace(day=1)
            month_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date__gte=month_start,
                created_at__date__lte=today
            )
            
            # Last 7 days sales trend
            week_ago = today - timedelta(days=7)
            week_sales = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date__gte=week_ago
            ).annotate(
                date=TruncDay('created_at')
            ).values('date').annotate(
                revenue=Sum('total_amount')
            ).order_by('date')
            
            sales_trend = []
            for day in week_sales:
                sales_trend.append({
                    'date': day['date'].strftime('%Y-%m-%d'),
                    'revenue': float(day['revenue'] or 0)
                })
            
            dashboard_data['modules']['sales_summary'] = {
                'today_sales': float(today_orders.aggregate(total=Sum('total_amount'))['total'] or 0),
                'today_orders': today_orders.count(),
                'month_sales': float(month_orders.aggregate(total=Sum('total_amount'))['total'] or 0),
                'month_orders': month_orders.count(),
                'sales_trend_7days': sales_trend
            }
        
        pending_pos = PurchaseOrder.objects.filter(
            company=company,
            status='ORDERED'
        )
        
        recent_pos = PurchaseOrder.objects.filter(
            company=company
        ).order_by('-created_at')[:5]
        
        dashboard_data['modules']['purchase_summary'] = {
            'pending_orders': pending_pos.count(),
            'pending_value': float(pending_pos.aggregate(total=Sum('total_amount'))['total'] or 0),
            'draft_orders': PurchaseOrder.objects.filter(company=company, status='DRAFT').count(),
            'recent_orders': [
                {
                    'id': po.id,
                    'order_number': po.order_number,
                    'vendor': po.vendor.display_name if po.vendor else 'N/A',
                    'total': float(po.total_amount),
                    'status': po.status,
                    'date': po.created_at.strftime('%Y-%m-%d')
                }
                for po in recent_pos
            ]
        }
        
        unread_alerts = InventoryAlert.objects.filter(
            company=company,
            is_read=False
        ).order_by('-created_at')[:10]
        
        dashboard_data['modules']['alerts'] = {
            'unread_count': InventoryAlert.objects.filter(company=company, is_read=False).count(),
            'recent_alerts': [
                {
                    'id': alert.id,
                    'type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'created_at': alert.created_at.strftime('%Y-%m-%d %H:%M')
                }
                for alert in unread_alerts
            ]
        }
        
        quick_actions = []
        
        if user_role in ['ADMIN', 'COMPANY_OWNER', 'STORE_MANAGER']:
            quick_actions.extend([
                {'label': 'Create Sales Order', 'url': '/inventory/orders/add/', 'icon': 'shopping-cart'},
                {'label': 'Add Product', 'url': '/inventory/products/add/', 'icon': 'package'}
            ])
        
        if user_role in ['ADMIN', 'COMPANY_OWNER', 'INVENTORY_MANAGER']:
            quick_actions.extend([
                {'label': 'Receive Purchase Order', 'url': '/inventory/purchase-orders/', 'icon': 'truck'},
                {'label': 'Adjust Stock', 'url': '/inventory/batch-stock/adjust/', 'icon': 'refresh-cw'}
            ])
        
        if user_role in ['ADMIN', 'COMPANY_OWNER']:
            quick_actions.extend([
                {'label': 'Add Vendor', 'url': '/inventory/vendors/add/', 'icon': 'users'},
                {'label': 'Generate Report', 'url': '/inventory/reports/', 'icon': 'bar-chart-2'}
            ])
        
        dashboard_data['modules']['quick_actions'] = quick_actions
        
        if user_role == 'ADMIN':
            # Multi-company stats for admin
            total_companies = Company.objects.count()
            total_users = UserProfile.objects.count()
            dashboard_data['modules']['admin_insights'] = {
                'total_companies': total_companies,
                'total_users': total_users,
                'system_status': 'healthy'
            }
        
        elif user_role == 'INVENTORY_MANAGER':
            # Focus on stock movement
            today_movements = StockTransaction.objects.filter(
                company=company,
                created_at__date=today
            ).count()
            
            dashboard_data['modules']['inventory_insights'] = {
                'today_movements': today_movements,
                'batches_to_check': near_expiry_batches.count() + expired_batches.count()
            }
        
        elif user_role == 'AUDITOR':
            # Audit trail summary
            recent_transactions = StockTransaction.objects.filter(
                company=company
            ).order_by('-created_at')[:5]
            
            dashboard_data['modules']['audit_summary'] = {
                'total_transactions_30days': StockTransaction.objects.filter(
                    company=company,
                    created_at__date__gte=today - timedelta(days=30)
                ).count(),
                'recent_activity': [
                    {
                        'id': t.id,
                        'user': t.created_by.username if t.created_by else 'System',
                        'action': f"{t.transaction_type} - {t.quantity} x {t.product.name if t.product else 'N/A'}",
                        'time': t.created_at.strftime('%Y-%m-%d %H:%M')
                    }
                    for t in recent_transactions
                ]
            }
        
        return Response(dashboard_data, status=status.HTTP_200_OK)



# 6. DASHBOARD WIDGET API (Individual widgets)

class DashboardWidgetAPIView(APIView):
    """
    API: GET /inventory/api/dashboard/widgets/{widget_name}/
    
    Returns data for individual dashboard widgets
    Widgets available:
        - stock_value
        - low_stock
        - near_expiry
        - sales_today
        - pending_orders
        - top_products
        - recent_activity
    
    Query Parameters:
        - widget: Widget name
        - company_id: Admin only
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, widget_name=None):
        company = get_user_company(request)
        if not company:
            return Response(
                {"error": "Company not found or access denied"},
                status=status.HTTP_404_NOT_FOUND
            )

        today = date.today()
        
        # Stock Value Widget
        if widget_name == 'stock_value':
            batches = ProductBatch.objects.filter(
                company=company,
                quantity__gt=0,
                is_active=True
            ).select_related('product')
            
            total_value = 0
            total_items = 0
            
            for batch in batches:
                if batch.product:
                    total_value += batch.quantity * float(batch.product.purchase_price or 0)
                    total_items += batch.quantity
            
            return Response({
                'widget': 'stock_value',
                'data': {
                    'total_value': round(total_value, 2),
                    'total_items': total_items,
                    'formatted_value': f"₹{round(total_value, 2):,}"
                }
            })
        
        # Low Stock Widget
        elif widget_name == 'low_stock':
            products = Product.objects.filter(company=company)
            low_stock_items = []
            
            for product in products:
                sellable_stock = ProductBatch.objects.filter(
                    company=company,
                    product=product,
                    expiry_date__gte=today,
                    quantity__gt=0,
                    is_active=True
                ).aggregate(total=Sum('quantity'))['total'] or 0
                
                if sellable_stock <= product.low_stock_limit:
                    low_stock_items.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'current_stock': sellable_stock,
                        'low_stock_limit': product.low_stock_limit,
                        'sku': product.sku
                    })
            
            return Response({
                'widget': 'low_stock',
                'data': {
                    'count': len(low_stock_items),
                    'items': low_stock_items[:10]  # Top 10
                }
            })
        
        # Near Expiry Widget
        elif widget_name == 'near_expiry':
            near_expiry_limit = today + timedelta(days=30)
            batches = ProductBatch.objects.filter(
                company=company,
                expiry_date__gte=today,
                expiry_date__lte=near_expiry_limit,
                quantity__gt=0,
                is_active=True
            ).select_related('product').order_by('expiry_date')[:10]
            
            items = []
            for batch in batches:
                items.append({
                    'batch_id': batch.id,
                    'batch_number': batch.batch_number,
                    'product_name': batch.product.name if batch.product else 'N/A',
                    'expiry_date': batch.expiry_date.strftime('%Y-%m-%d'),
                    'days_left': (batch.expiry_date - today).days,
                    'quantity': batch.quantity
                })
            
            return Response({
                'widget': 'near_expiry',
                'data': {
                    'total_count': ProductBatch.objects.filter(
                        company=company,
                        expiry_date__gte=today,
                        expiry_date__lte=near_expiry_limit,
                        quantity__gt=0,
                        is_active=True
                    ).count(),
                    'items': items
                }
            })
        
        # Sales Today Widget
        elif widget_name == 'sales_today':
            if get_user_role(request) in ['INVENTORY_MANAGER']:
                return Response({'widget': 'sales_today', 'data': {'access_denied': True}})
            
            today_orders = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date=today
            )
            
            total_sales = today_orders.aggregate(total=Sum('total_amount'))['total'] or 0
            order_count = today_orders.count()
            
            # Compare with yesterday
            yesterday = today - timedelta(days=1)
            yesterday_sales = SalesOrder.objects.filter(
                company=company,
                status='DELIVERED',
                created_at__date=yesterday
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            
            growth = 0
            if yesterday_sales > 0:
                growth = ((total_sales - yesterday_sales) / yesterday_sales) * 100
            
            return Response({
                'widget': 'sales_today',
                'data': {
                    'total_sales': round(float(total_sales), 2),
                    'order_count': order_count,
                    'growth_percentage': round(growth, 2),
                    'formatted_sales': f"₹{round(float(total_sales), 2):,}"
                }
            })
        
        # Default: Return all widget names
        else:
            return Response({
                'widgets': [
                    'stock_value',
                    'low_stock',
                    'near_expiry',
                    'sales_today',
                    'pending_orders',
                    'top_products',
                    'recent_activity'
                ],
                'endpoint': '/inventory/api/dashboard/widgets/{widget_name}/'
            })