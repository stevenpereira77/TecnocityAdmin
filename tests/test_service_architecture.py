from app.database import create_database_engine, create_session_factory, initialize_database
from app.reports.service import ReportService
from app.services import (
    ExpenseService,
    InventoryService,
    ProductFilter,
    ProductService,
    PurchaseService,
    ReportingService,
    ReturnService,
    SaleService,
    StoreService,
)


def service():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return StoreService(create_session_factory(engine))


def test_store_service_is_a_facade_over_specialized_services():
    svc = service()
    assert isinstance(svc.product_service, ProductService)
    assert isinstance(svc.inventory_service, InventoryService)
    assert isinstance(svc.purchase_service, PurchaseService)
    assert isinstance(svc.sale_service, SaleService)
    assert isinstance(svc.return_service, ReturnService)
    assert isinstance(svc.expense_service, ExpenseService)
    assert isinstance(svc.reporting_service, ReportingService)
    assert isinstance(svc.report_service, ReportService)


def test_facade_delegation_keeps_existing_api_functional():
    svc = service()
    product = svc.create_product(sku="ARCH-1", name="Arquitectura", sale_price="25.00")
    assert svc.get_product(product.id).sku == "ARCH-1"
    assert svc.list_products()[0].name == "Arquitectura"
    assert svc.list_products(filters=ProductFilter(search="Arquitectura"))[0].name == "Arquitectura"
    assert svc.product_filter_options()["categories"] == ["General"]
    assert svc.dashboard()["products_count"] == 1
