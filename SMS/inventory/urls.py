from django.urls import path
from . import views

from .views import all_transactions,add_stock, export_inventory_velocity_xls, submit_purchase_order, NearExpiryReportAPIView, PurchaseStockReportAPIView, fast_slow_products_view, near_expiry_report_view, NearExpiryProductReportView, fast_slow_products_api
from .views import PurchaseStockReportAPIView
from .views import StockSummaryAPIView, AvailableVsReservedStockAPIView
from .views import (
    ExpiryWiseStockAPIView, 
    StockValuationAPIView, 
    OutOfStockAPIView, 
    NearExpiryReportAPIView,
    StockSummaryAPIView,
    AvailableVsReservedStockAPIView,
    fast_slow_products_api,
    profit_margin_report_api,
    products_by_category_api,
)
urlpatterns = [

    # ---------- PRODUCTS ----------
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.add_product, name="add_product"),
    path("products/edit/<int:pk>/", views.edit_product, name="edit_product"),
    path("products/delete/<int:pk>/", views.delete_product, name="delete_product"),

    # ---------- CATEGORIES ----------
    path("categories/", views.category_list, name="category_list"),
    path("categories/edit/<int:pk>/", views.edit_category, name="edit_category"),
    path("categories/delete/<int:pk>/", views.delete_category, name="delete_category"),

    # ---------- SALES ORDERS ----------
    path("orders/", views.sales_order_list, name="sales_orders"),
    path("orders/add/", views.add_sales_order, name="add_sales_order"),
    path("orders/<int:pk>/", views.sales_order_detail, name="sales_order_detail"),
    path("orders/<int:pk>/status/", views.update_order_status, name="update_order_status"),
    path("orders/<int:pk>/cancel/", views.cancel_and_reverse_sales_order, name="cancel_and_reverse_sales_order"),

    # ---------- PURCHASE ----------
    path("vendors/", views.vendor_list, name="vendor_list"),
    path("vendors/add/", views.add_vendor, name="add_vendor"),
    path("vendors/edit/<int:pk>/", views.edit_vendor, name="edit_vendor"),
    path("vendors/delete/<int:pk>/", views.delete_vendor, name="delete_vendor"),

    path("purchase-orders/", views.purchase_order_list, name="purchase_orders"),
    path("purchase-orders/add/", views.add_purchase_order, name="add_purchase_order"),
    path("purchase-orders/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
    # path("purchase-orders/<int:pk>/receive/", views.receive_purchase_order, name="receive_purchase_order"),

    path("reports/", views.reports_view, name="reports"),
    path("reports/export/excel/", views.export_sales_excel, name="export_sales_excel"),
    path("reports/export/pdf/", views.export_sales_pdf, name="export_sales_pdf"),

    path("transactions/", all_transactions, name="all_transactions"),
    path("stock/add/", add_stock, name="add_stock"),


    path("reports/stock-movement/", views.stock_movement_report, name="stock_movement_report"),
    path('customers/export/', views.customer_export_excel, name='customer_export_excel'),
    path("quotes/", views.quote_list, name="quote_list"),
    path("quotes/create/", views.quote_create, name="quote_create"),

    path("batches/",views.batch_stock_list,name="batch_stock_list"),

    path("vendors/export/", views.export_vendors_csv, name="export_vendors_csv"),

    path("inventory/batch-stock/adjust/",views.adjust_batch_stock,name="adjust_batch_stock"),

    path('purchase-orders/', views.purchase_order_list, name='purchase_orders'),
    path('purchase-orders/<int:pk>/print/',views.purchase_order_print,name='purchase_order_print'),
    
    path("inventory/purchase-orders/<int:pk>/print/",views.purchase_order_print,name="purchase_order_print"),
    path(
    "purchase-orders/<int:pk>/delete/",
    views.delete_purchase_order,
    name="delete_purchase_order"
    ),
    path(
        "purchase-orders/export/pdf/",
        views.export_purchase_orders_pdf,
        name="export_purchase_orders_pdf"
    ),

    path(
        "vendors/export/pdf/",
        views.export_vendors_pdf,
        name="export_vendors_pdf"
    ),

    path(
        "sales-orders/export/pdf/",
        views.export_sales_orders_pdf,
        name="export_sales_orders_pdf"
    ),
    
    path(
        "inventory/export/pdf/",
        views.export_inventory_pdf,
        name="export_inventory_pdf"
    ),

    path(
        "inventory/batch-stock/export/pdf/",
        views.export_batch_stock_pdf,
        name="export_batch_stock_pdf"
    ),

    path("batch-stock/get-stock/", views.get_batch_stock, name="get_batch_stock"),
    path("inventory/stock-aging/", views.stock_aging_report, name="stock_aging_report"),

    path("inventory/product/<int:pk>/batches/",
     views.product_stock_breakdown,
     name="product_stock_breakdown"),

    path("ajax/fefo-preview/", views.fefo_preview_api, name="fefo_preview_api"),


    path('customers/export/', views.customer_export_excel, name='customer_export_excel'),
    path("customers/add/", views.customer_create, name="customer_add"),
    path('customers/', views.customer_list, name='customer_list'), 
    path('inventory/customers/delete/<int:pk>/', views.customer_delete, name='customer_delete'),
    path('inventory/customers/edit/<int:pk>/', views.customer_edit, name='customer_edit'),

    path(
    "inventory/reports/fast-slow/",views.fast_slow_products_report,name="fast_slow_products_report"),
    

    path("inventory/alerts/",views.inventory_alerts,name="inventory_alerts"),

    path("inventory/reorder-suggestions/",views.reorder_suggestions,name="reorder_suggestions"),


    path(
    "inventory/export-velocity-xls/",
    export_inventory_velocity_xls,
    name="export_inventory_velocity_xls"
),


path(
    "batch-stock/get-batches/",
    views.get_batches_by_product,
    name="get_batches_by_product"
),

path(
    "purchase-orders/<int:pk>/delete/",
    views.delete_purchase_order,
    name="delete_purchase_order"
),

path(
    "purchase-orders/<int:pk>/submit/",
    submit_purchase_order,
    name="submit_purchase_order"
),

path("alerts/mark-read/", views.mark_alerts_read, name="mark_alerts_read"),

#31-01-26
 path(
        "reports/near-expiry/",
        views.near_expiry_report,
        name="near_expiry_report"
    ),

path( "api/stocks/near-expiry/",
        NearExpiryReportAPIView.as_view(),
        name="near-expiry-report-api"
),

path(
        "reports/purchase-stock/",
        PurchaseStockReportAPIView.as_view(),
        name="purchase-stock-report",
    ),

path(
        "reports/purchase-stock/view/",
        views.purchase_stock_report_view,  # Use views.purchase_stock_report_view
        name="purchase_stock_report_view",
    ),

path(
        "fast-slow-products/",
        fast_slow_products_view,
        name="fast_slow_products_view"
    ),

    # Backend API JSON endpoint
    path(
        "api/fast-slow-products/",
        fast_slow_products_api,
        name="fast_slow_products_api"
    ),

path('reports/supplier-performance/', views.supplier_performance, name='supplier_performance'),

path(
    'reports/near-expiry/',
    NearExpiryProductReportView.as_view(),
    name='near-expiry-report'
),

path(
        'reports/near-expiry/view/',
        near_expiry_report_view,
        name='near_expiry_report_view'
    ),

# PROFIT MARGIN REPORT
    path(
        "reports/profit-margin/",
        views.profit_margin_report_view,
        name="profit_margin_report"
    ),

    path(
        "api/reports/profit-margin/",
        views.profit_margin_report_api,
        name="profit_margin_report_api"
    ),

    path(
        "api/products-by-category/",
        views.products_by_category_api,
        name="products_by_category_api"
    ),

path("reports/supplier-performance/", views.supplier_performance, name="supplier_performance"),

path("reports/expired-stock/", views.expired_stock_report, name="expired_stock_report"),

path(
        'product/<int:id>/batches/export/',
        views.export_inventory_pdf,
        name='export_inventory_pdf'
    ),

path('inventory/history/<int:pk>/', views.inventory_history, name='inventory_history'),


path(
        "api/products-list/",
        views.products_list_api,
        name="products_list_api"
    ),

    path(
        "api/categories-list/",
        views.categories_list_api,
        name="categories_list_api"
    ),

    # Option 1: Clean /api/ prefix
    path("api/stock/summary/", StockSummaryAPIView.as_view(), name="stock_summary_api"),
    path("api/stock/available-vs-reserved/", AvailableVsReservedStockAPIView.as_view(), name="available_vs_reserved_api"),
    
   
    path("inventory/api/stock/summary/", StockSummaryAPIView.as_view(), name="inventory_stock_summary_api"),
    path("inventory/api/stock/available-vs-reserved/", AvailableVsReservedStockAPIView.as_view(), name="inventory_available_vs_reserved_api"),
    # Add these with your other API endpoints
    path("api/stocks/expiry-wise/", ExpiryWiseStockAPIView.as_view(), name="expiry-wise-stock"),
    path("api/stocks/valuation/", StockValuationAPIView.as_view(), name="stock-valuation"),
    path("api/stocks/out-of-stock/", OutOfStockAPIView.as_view(), name="out-of-stock-api"),


     # 1. STOCK IN REPORTS (Purchases, Returns)
    path(
        "api/reports/stock-in/",
        views.StockInReportAPIView.as_view(),
        name="stock_in_report_api"
    ),
    
    # 2. STOCK OUT REPORTS (Sales, Damages, Expiry)
    path(
        "api/reports/stock-out/",
        views.StockOutReportAPIView.as_view(),
        name="stock_out_report_api"
    ),
    
    # 3. ADJUSTMENT HISTORY
    path(
        "api/reports/adjustments/",
        views.AdjustmentHistoryAPIView.as_view(),
        name="adjustment_history_api"
    ),
    
    # 4. DATE-WISE STOCK MOVEMENT
    path(
        "api/reports/date-wise-movement/",
        views.DateWiseMovementAPIView.as_view(),
        name="date_wise_movement_api"
    ),
    
    # 5. USER-WISE STOCK ACTIVITY
    path(
        "api/reports/user-activity/",
        views.UserActivityAPIView.as_view(),
        name="user_activity_api"
    ),
    
    # 6. TRANSACTION REFERENCE REPORTS (PO, GRN, Invoice)
    path(
        "api/reports/transaction-reference/",
        views.TransactionReferenceAPIView.as_view(),
        name="transaction_reference_api"
    ),
    
    # 7. COMPREHENSIVE STOCK MOVEMENT REPORT (All filters)
    path(
        "api/reports/stock-movement/",
        views.StockMovementReportAPIView.as_view(),
        name="stock_movement_report_api"),

     # 1. Near-expiry products report (configurable threshold)
    path(
        "api/reports/near-expiry-products/",
        views.NearExpiryProductsReportAPIView.as_view(),
        name="near_expiry_products_report_api"
    ),
    
    # 2. Expired stock report
    path(
        "api/reports/expired-stock/",
        views.ExpiredStockReportAPIView.as_view(),
        name="expired_stock_report_api"
    ),
    
    # 3. FEFO compliance report
    path(
        "api/reports/fefo-compliance/",
        views.FEFOComplianceReportAPIView.as_view(),
        name="fefo_compliance_report_api"
    ),
    
    # 4. Blocked expired stock sales report
    path(
        "api/reports/blocked-expired-sales/",
        views.BlockedExpiredSalesReportAPIView.as_view(),
        name="blocked_expired_sales_report_api"
    ),
    
    # 5. Loss due to expiry (value-based)
    path(
        "api/reports/loss-due-to-expiry/",
        views.LossDueToExpiryReportAPIView.as_view(),
        name="loss_due_to_expiry_report_api"
    ),
    
    # 6. Expiry summary dashboard API
    path(
        "api/reports/expiry-summary/",
        views.ExpirySummaryDashboardAPIView.as_view(),
        name="expiry_summary_api"
    ),



    # 1. Daily/Weekly/Monthly Sales Report
    path(
        "api/reports/sales/periodic/",
        views.SalesPeriodicReportAPIView.as_view(),
        name="sales_periodic_report_api"
    ),
    
    # 2. Product-wise Sales Report
    path(
        "api/reports/sales/product-wise/",
        views.ProductWiseSalesReportAPIView.as_view(),
        name="product_wise_sales_report_api"
    ),
    
    # 3. Category-wise Sales Report
    path(
        "api/reports/sales/category-wise/",
        views.CategoryWiseSalesReportAPIView.as_view(),
        name="category_wise_sales_report_api"
    ),
    
    # 4. Batch-wise Sales Report
    path(
        "api/reports/sales/batch-wise/",
        views.BatchWiseSalesReportAPIView.as_view(),
        name="batch_wise_sales_report_api"
    ),
    
    # 5. Refund & Return Report
    path(
        "api/reports/sales/refunds/",
        views.RefundReturnReportAPIView.as_view(),
        name="refund_return_report_api"
    ),
    
    # 6. Margin Report (Selling vs Purchase Price)
    path(
        "api/reports/sales/margin/",
        views.MarginReportAPIView.as_view(),
        name="margin_report_api"
    ),
    
    # 7. Sales Dashboard Summary
    path(
        "api/reports/sales/dashboard/",
        views.SalesDashboardSummaryAPIView.as_view(),
        name="sales_dashboard_summary_api"
    ),
# Add these to your existing urlpatterns

    # 1. Key KPIs Dashboard
    path(
        "api/dashboard/kpis/",
        views.DashboardKPIsAPIView.as_view(),
        name="dashboard_kpis_api"
    ),
    
    # 2. Sales Trends Chart
    path(
        "api/dashboard/charts/sales-trends/",
        views.SalesTrendsChartAPIView.as_view(),
        name="sales_trends_chart_api"
    ),
    
    # 3. Stock Movement Trends Chart
    path(
        "api/dashboard/charts/stock-movement/",
        views.StockMovementTrendsChartAPIView.as_view(),
        name="stock_movement_chart_api"
    ),
    
    # 4. Category Contribution Chart
    path(
        "api/dashboard/charts/category-contribution/",
        views.CategoryContributionChartAPIView.as_view(),
        name="category_contribution_chart_api"
    ),
    
    # 5. Role-based Dashboard (Complete)
    path(
        "api/dashboard/",
        views.RoleBasedDashboardAPIView.as_view(),
        name="role_based_dashboard_api"
    ),
    
    # 6. Dashboard Widgets (Individual)
    path(
        "api/dashboard/widgets/<str:widget_name>/",
        views.DashboardWidgetAPIView.as_view(),
        name="dashboard_widget_api"
    ),
path('export-inventory-pdf/', views.export_inventory_pdf, name='export_inventory_pdf'),

path(
    "reports/abc-classification/",
    views.abc_inventory_classification,
    name="abc_inventory_classification"
),


path('products/bulk-delete/', views.bulk_delete_products, name='bulk_delete_products'),

path("stock-movement/<int:pk>/", views.inventory_history, name="stock_movement_report"), 

path('export-product-pdf/<int:pk>/', views.export_product_pdf, name='export_product_pdf'),

]