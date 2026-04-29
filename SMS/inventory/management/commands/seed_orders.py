from django.core.management.base import BaseCommand
from decimal import Decimal
from faker import Faker
import random

from company.models import Company

from inventory.models import (
    Category,
    Product,
    Vendor,
    ProductBatch,
    PurchaseOrder,
    PurchaseOrderItem,
    SalesOrder,
    SalesOrderItem
)

fake = Faker()


class Command(BaseCommand):

    help = "Generate realistic stock flow demo data"

    def handle(self,*args,**kwargs):

        company = Company.objects.first()

        if not company:
            print("Create company first")
            return


        CATEGORY_COUNT = 20
        PRODUCT_COUNT  = 500
        VENDOR_COUNT   = 200

        PURCHASE_COUNT = 100000
        SALES_COUNT    = 100000

        BATCH_SIZE = 10000


        ####################################################
        # CATEGORIES
        ####################################################

        print("Creating Categories...")

        categories=[]

        for i in range(CATEGORY_COUNT):
            categories.append(
                Category(
                    company=company,
                    name=f"Category-{i}"
                )
            )

        Category.objects.bulk_create(
            categories,
            ignore_conflicts=True
        )

        categories=list(
            Category.objects.filter(
                company=company
            )
        )


        ####################################################
        # PRODUCTS
        ####################################################

        print("Creating Products...")

        products=[]

        for i in range(PRODUCT_COUNT):

            cost=Decimal(
                random.randint(
                    100,
                    2000
                )
            )

            sell=cost+Decimal(
                random.randint(
                    50,
                    500
                )
            )


            products.append(
                Product(
                    company=company,
                    category=random.choice(
                        categories
                    ),
                    name=f"Product-{i}"[:50],
                    product_company=fake.company()[:100],
                    sku=f"SKU-{100000+i}",
                    purchase_price=cost,
                    selling_price=sell,
                    stock_quantity=0
                )
            )

        Product.objects.bulk_create(
            products,
            batch_size=BATCH_SIZE,
            ignore_conflicts=True
        )


        products=list(
            Product.objects.filter(
                company=company
            )
        )



        ####################################################
        # VENDORS
        ####################################################

        print("Creating Vendors...")

        vendors=[]

        for i in range(VENDOR_COUNT):

            gst=(
                f"{random.randint(10,99)}"
                f"ABCDE"
                f"{random.randint(1000,9999)}"
                f"A1Z5"
            )

            vendors.append(
                Vendor(
                    company=company,
                    first_name=fake.first_name()[:20],
                    last_name=fake.last_name()[:20],
                    company_name=fake.company()[:50],
                    display_name=f"Vendor-{i}"[:50],
                    gst_number=gst,
                    email=f"vendor{i}@mail.com",
                    mobile=str(
                        random.randint(
                            6000000000,
                            9999999999
                        )
                    ),
                    address=fake.address()[:300],
                    status="A"
                )
            )

        Vendor.objects.bulk_create(
            vendors,
            batch_size=5000,
            ignore_conflicts=True
        )


        vendors=list(
            Vendor.objects.filter(
                company=company
            )
        )



        ####################################################
        # PURCHASE ORDERS
        ####################################################

        print("Creating Purchase Orders...")

        po_buffer=[]

        for i in range(PURCHASE_COUNT):

            po_buffer.append(
                PurchaseOrder(
                    company=company,

                    vendor=random.choice(
                        vendors
                    ),

                    order_number=f"PO-{100000+i}",

                    status=random.choices(
                        [
                            "RECEIVED",
                            "PARTIAL",
                            "ORDERED"
                        ],
                        weights=[70,20,10]
                    )[0],

                    total_amount=0
                )
            )


            if len(po_buffer)>=BATCH_SIZE:

                PurchaseOrder.objects.bulk_create(
                    po_buffer,
                    batch_size=BATCH_SIZE
                )

                print(
                    f"{i} purchase inserted"
                )

                po_buffer=[]


        if po_buffer:
            PurchaseOrder.objects.bulk_create(
                po_buffer
            )


        purchase_orders=list(
            PurchaseOrder.objects.order_by(
                "-id"
            )[:PURCHASE_COUNT]
        )



        ####################################################
        # RECEIVE PO + PRODUCT BATCHES
        ####################################################

        print(
            "Receiving Purchase Orders..."
        )

        po_items=[]
        batch_rows=[]
        po_updates=[]

        inventory={}

        for p in products:
            inventory[p.id]=0


        for order in purchase_orders:

            total=Decimal("0")

            lines=random.randint(
                1,
                5
            )

            for line_no in range(lines):

                product=random.choice(
                    products
                )

                qty=random.randint(
                    100,
                    1000
                )

                received_qty=qty


                if order.status=="PARTIAL":
                    received_qty=int(
                        qty*0.60
                    )

                elif order.status=="ORDERED":
                    received_qty=0


                cost=product.purchase_price

                total+=qty*cost


                ################################################
                # UNIQUE BATCH NUMBER FIX
                ################################################

                batch_no=(
                    f"PO{order.id}"
                    f"-PR{product.id}"
                    f"-LN{line_no}"
                )


                po_items.append(
                    PurchaseOrderItem(
                        order=order,
                        product=product,
                        quantity=qty,
                        received_quantity=received_qty,
                        cost_price=cost,
                        batch_number=batch_no
                    )
                )


                if received_qty>0:

                    batch_rows.append(
                        ProductBatch(
                            company=company,
                            product=product,
                            batch_number=batch_no,
                            quantity=received_qty,
                            is_active=True
                        )
                    )

                    inventory[
                        product.id
                    ] += received_qty


            order.total_amount=total

            po_updates.append(
                order
            )



            if len(po_items)>=BATCH_SIZE:

                PurchaseOrderItem.objects.bulk_create(
                    po_items,
                    batch_size=BATCH_SIZE
                )

                po_items=[]



            if len(batch_rows)>=BATCH_SIZE:

                ProductBatch.objects.bulk_create(
                    batch_rows,
                    batch_size=BATCH_SIZE,
                    ignore_conflicts=True
                )

                batch_rows=[]



        if po_items:
            PurchaseOrderItem.objects.bulk_create(
                po_items
            )


        if batch_rows:
            ProductBatch.objects.bulk_create(
                batch_rows,
                ignore_conflicts=True
            )



        PurchaseOrder.objects.bulk_update(
            po_updates,
            ['total_amount'],
            batch_size=5000
        )



        ####################################################
        # UPDATE PRODUCT STOCK
        ####################################################

        print(
            "Updating Product Stock..."
        )

        for p in products:
            p.stock_quantity=inventory[
                p.id
            ]

        Product.objects.bulk_update(
            products,
            ['stock_quantity'],
            batch_size=5000
        )



        ####################################################
        # SALES ORDERS
        ####################################################

        print("Creating Sales Orders...")

        sales=[]

        for i in range(SALES_COUNT):

            sales.append(
                SalesOrder(
                    company=company,

                    order_number=f"SO-{100000+i}",

                    customer_name=fake.name()[:100],

                    status=random.choices(
                        [
                            "DELIVERED",
                            "PROCESSING",
                            "PENDING"
                        ],
                        weights=[60,30,10]
                    )[0],

                    total_amount=0
                )
            )


            if len(sales)>=BATCH_SIZE:

                SalesOrder.objects.bulk_create(
                    sales,
                    batch_size=BATCH_SIZE
                )

                print(
                    f"{i} sales inserted"
                )

                sales=[]


        if sales:
            SalesOrder.objects.bulk_create(
                sales
            )


        sales_orders=list(
            SalesOrder.objects.order_by(
                "-id"
            )[:SALES_COUNT]
        )



        ####################################################
        # SALES ITEMS + STOCK REDUCE
        ####################################################

        print(
            "Creating Sales..."
        )

        so_items=[]
        so_updates=[]


        available_products=[
            p for p in products
            if inventory[p.id]>0
        ]


        for order in sales_orders:

            total=Decimal("0")

            lines=random.randint(
                1,
                5
            )

            for _ in range(lines):

                product=random.choice(
                    available_products
                )

                available=inventory[
                    product.id
                ]

                if available<=0:
                    continue


                qty=random.randint(
                    1,
                    min(
                        50,
                        available
                    )
                )


                inventory[
                    product.id
                ] -= qty


                price=product.selling_price

                total+=qty*price


                so_items.append(
                    SalesOrderItem(
                        order=order,
                        product=product,
                        quantity=qty,
                        price=price
                    )
                )


            order.total_amount=total

            so_updates.append(
                order
            )



            if len(so_items)>=BATCH_SIZE:

                SalesOrderItem.objects.bulk_create(
                    so_items,
                    batch_size=BATCH_SIZE
                )

                so_items=[]



        if so_items:
            SalesOrderItem.objects.bulk_create(
                so_items
            )



        SalesOrder.objects.bulk_update(
            so_updates,
            ['total_amount'],
            batch_size=BATCH_SIZE
        )



        ####################################################
        # FINAL STOCK UPDATE
        ####################################################

        print(
            "Updating Remaining Stock..."
        )

        for p in products:
            p.stock_quantity=inventory[
                p.id
            ]

        Product.objects.bulk_update(
            products,
            ['stock_quantity'],
            batch_size=5000
        )



        ####################################################
        # SUMMARY
        ####################################################

        print("\nDONE SUCCESSFULLY\n")

        print(
            "Categories:",
            Category.objects.count()
        )

        print(
            "Products:",
            Product.objects.count()
        )

        print(
            "Product Batches:",
            ProductBatch.objects.count()
        )

        print(
            "Vendors:",
            Vendor.objects.count()
        )

        print(
            "Purchase Orders:",
            PurchaseOrder.objects.count()
        )

        print(
            "Purchase Items:",
            PurchaseOrderItem.objects.count()
        )

        print(
            "Sales Orders:",
            SalesOrder.objects.count()
        )

        print(
            "Sales Items:",
            SalesOrderItem.objects.count()
        )