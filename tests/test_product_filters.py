from datetime import datetime
from decimal import Decimal

import pytest

from app.database import create_database_engine, create_session_factory, initialize_database
from app.services import ProductFilter, ProductService, StoreService


def service():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    return StoreService(create_session_factory(engine))


def seed(svc):
    return [
        svc.create_product(sku="A-100", name="Alpha Phone", category="Telefonia", brand="Alpha", sale_price="500.00", stock_min=3),
        svc.create_product(sku="B-200", name="Beta Cable", category="Accesorios", brand="Beta", sale_price="25.00", stock_min=2),
        svc.create_product(sku="C-300", name="Gamma Case", category="Accesorios", brand="Gamma", sale_price="75.00", stock_min=1),
        svc.create_product(sku="D-400", name="Delta Phone", category="Telefonia", brand="Alpha", sale_price="950.00", stock_min=5),
    ]


def test_product_filter_search_covers_multiple_catalog_fields():
    svc = service()
    products = seed(svc)
    assert [p.id for p in svc.list_products(filters=ProductFilter(search="Alpha"))] == [products[0].id, products[3].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(search="B-200"))] == [products[1].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(search=str(products[2].id)))] == [products[2].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(search="Accesorios"))] == [products[1].id, products[2].id]


def test_product_filter_can_filter_exact_and_id_ranges():
    svc = service()
    products = seed(svc)
    assert [p.id for p in svc.list_products(filters=ProductFilter(product_id=products[2].id))] == [products[2].id]
    filtered = svc.list_products(filters=ProductFilter(id_min=products[1].id, id_max=products[3].id))
    assert [p.id for p in filtered] == [products[1].id, products[2].id, products[3].id]


def test_product_filter_category_brand_price_and_stock_state():
    svc = service()
    products = seed(svc)
    # Create inventory so stock-state filters are meaningful.
    svc.adjust_stock(product_id=products[0].id, quantity=5, reason="seed")
    svc.adjust_stock(product_id=products[1].id, quantity=1, reason="seed")

    filters = ProductFilter(category="Telefonia", brand="Alpha", price_min=Decimal("600"), price_max=Decimal("1000"), sort_by="sale_price", sort_direction="desc")
    assert [p.id for p in svc.list_products(filters=filters)] == [products[3].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(stock_status="in_stock", sort_by="id"))] == [products[0].id, products[1].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(stock_status="low", sort_by="id"))] == [products[1].id]
    assert [p.id for p in svc.list_products(filters=ProductFilter(stock_status="out", sort_by="id"))] == [products[2].id, products[3].id]


def test_product_filter_sorting_supports_asc_and_desc_by_price_and_id():
    svc = service()
    products = seed(svc)
    assert [p.sale_price for p in svc.list_products(filters=ProductFilter(sort_by="sale_price", sort_direction="asc"))] == [Decimal("25.00"), Decimal("75.00"), Decimal("500.00"), Decimal("950.00")]
    assert [p.id for p in svc.list_products(filters=ProductFilter(sort_by="id", sort_direction="desc"))] == sorted([p.id for p in products], reverse=True)


def test_product_filter_validation_rejects_invalid_ranges_and_sorting():
    with pytest.raises(ValueError):
        ProductFilter(id_min=10, id_max=5)
    with pytest.raises(ValueError):
        ProductFilter(price_min=Decimal("100"), price_max=Decimal("50"))
    with pytest.raises(ValueError):
        ProductFilter(sort_by="unknown")
    with pytest.raises(ValueError):
        ProductFilter(sort_direction="sideways")


def test_product_filter_options_are_distinct_and_sorted():
    svc = service()
    seed(svc)
    svc.create_product(sku="E-500", name="Epsilon", category="Telefonia", brand="Alpha", sale_price="1")
    options = svc.product_filter_options()
    assert options["categories"] == ["Accesorios", "Telefonia"]
    assert options["brands"] == ["Alpha", "Beta", "Gamma"]


def test_legacy_list_products_api_remains_compatible():
    svc = service()
    products = seed(svc)
    assert [p.id for p in svc.list_products(search="Gamma")] == [products[2].id]
    assert [p.name for p in svc.list_products(active_only=True)] == ["Alpha Phone", "Beta Cable", "Delta Phone", "Gamma Case"]
