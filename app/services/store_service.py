"""Backward-compatible application service facade.

The original monolithic StoreService has been split into focused domain
services. This facade keeps the existing GUI/API stable while delegating all
business logic to the specialized services.
"""
from __future__ import annotations

from datetime import datetime
from app.services.constants import (
    DELIVERY_STATUSES,
    SALE_CANCELLED,
    SALE_CONFIRMED,
    SALE_INACTIVE,
    SALE_PARTIAL_RETURN,
    SALE_RETURNED,
    SHIPPING_CUSTOMER_DIRECT,
    SHIPPING_CUSTOMER_ORDER,
    SHIPPING_PAYER_LABELS,
    SHIPPING_STORE,
)
from app.services.expense_service import ExpenseService
from app.services.inventory_service import InventoryService
from app.services.product_filters import ProductFilter
from app.services.product_service import ProductService
from app.services.purchase_service import PurchaseService
from app.services.reporting_service import ReportingService
from app.services.return_service import ReturnService
from app.services.sale_service import SaleService
from app.reports.service import ReportService


class StoreService:
    """Compatibility facade over specialized domain services.

    New code can depend directly on ``products``, ``inventory``, ``purchases``,
    ``sales``, ``expenses`` or ``reports``. Existing callers can keep using the
    historical StoreService methods without any behavior change.
    """

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.inventory_service = InventoryService(session_factory)
        self.product_service = ProductService(session_factory)
        self.purchase_service = PurchaseService(session_factory, self.inventory_service)
        self.sale_service = SaleService(session_factory, self.inventory_service)
        self.return_service = ReturnService(session_factory, self.inventory_service)
        self.expense_service = ExpenseService(session_factory)
        self.reporting_service = ReportingService(session_factory)
        self.report_service = ReportService(session_factory)

    # ---------- Catalog facade ----------
    def list_products(self, search: str = "", active_only: bool = False, filters: ProductFilter | None = None):
        return self.product_service.list_products(search=search, active_only=active_only, filters=filters)

    def count_products(self, filters: ProductFilter | None = None):
        return self.product_service.count_products(filters=filters)

    def list_products_page(self, filters: ProductFilter | None = None, *, page: int = 1, page_size: int = 100):
        return self.product_service.list_products_page(filters=filters, page=page, page_size=page_size)

    def product_filter_options(self):
        return self.product_service.filter_options()

    def create_product(self, **kwargs):
        return self.product_service.create_product(**kwargs)

    def update_product(self, product_id: int, **data):
        return self.product_service.update_product(product_id, **data)

    def toggle_product(self, product_id: int) -> None:
        self.product_service.toggle_product(product_id)

    def get_product(self, product_id: int):
        return self.product_service.get_product(product_id)

    # ---------- Purchase facade ----------
    def register_purchase(self, **kwargs):
        return self.purchase_service.register_purchase(**kwargs)

    def preview_purchase(self, **kwargs):
        return self.purchase_service.preview_purchase(**kwargs)

    # ---------- Sales facade ----------
    def register_sale(self, **kwargs):
        return self.sale_service.register_sale(**kwargs)

    def preview_sale(self, **kwargs):
        return self.sale_service.preview_sale(**kwargs)

    def get_sale(self, sale_id: int):
        return self.sale_service.get_sale(sale_id)

    def get_sale_by_number(self, number: str):
        return self.sale_service.get_sale_by_number(number)

    def sale_summary(self, sale_id: int):
        return self.sale_service.sale_summary(sale_id)

    def update_delivery_status(self, sale_id: int, delivery_status: str):
        return self.sale_service.update_delivery_status(sale_id, delivery_status)

    def return_sale(self, **kwargs):
        return self.return_service.return_sale(**kwargs)

    def cancel_sale(self, **kwargs):
        return self.return_service.cancel_sale(**kwargs)

    def effective_sale_values(self, sale):
        """Return sale totals after refunds through the owning return service."""
        return self.return_service.effective_sale_values(sale)

    # ---------- Expense facade ----------
    def register_expense(self, **kwargs):
        return self.expense_service.register_expense(**kwargs)

    # ---------- Inventory facade ----------
    def adjust_stock(self, **kwargs):
        return self.inventory_service.adjust_stock(**kwargs)

    def inventory_rows(self, *, limit: int | None = None, offset: int = 0):
        return self.inventory_service.inventory_rows(limit=limit, offset=offset)

    def inventory_count(self):
        return self.inventory_service.inventory_count()

    def movements(self, product_id: int | None = None, limit: int = 100):
        return self.inventory_service.movements(product_id, limit=limit)

    # ---------- Read/report facade ----------
    def purchases(self, limit: int = 100):
        return self.reporting_service.purchases(limit)

    def sales(self, limit: int = 100):
        return self.reporting_service.sales(limit)

    def expenses(self, limit: int = 100):
        return self.reporting_service.expenses(limit)

    def audit_logs(self, limit: int = 150):
        return self.reporting_service.audit_logs(limit)

    def dashboard(self, now: datetime | None = None):
        return self.reporting_service.dashboard(now)

    def dashboard_report(self, **kwargs):
        return self.reporting_service.dashboard_report(**kwargs)

    def report_definitions(self):
        return self.report_service.definitions()

    def build_report(self, report_key: str, **kwargs):
        return self.report_service.build(report_key, **kwargs)
