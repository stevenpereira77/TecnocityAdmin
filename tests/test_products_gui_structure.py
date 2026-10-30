import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_products_page_contains_advanced_filters_and_server_side_spec():
    source = (ROOT / "app" / "widgets" / "products_page.py").read_text(encoding="utf-8")
    assert "class ProductsPage" in source
    for token in ("ProductFilter", "Filtros avanzados", "Todas las categorías", "Todas las marcas", "Stock bajo", "Agotados", "Precio desde", "Precio hasta", "ID exacto", "ID desde", "ID hasta", "Ascendente ↑", "Descendente ↓", "Limpiar filtros"):
        assert token in source
    tree = ast.parse(source)
    assert not any(isinstance(node, ast.For) and isinstance(node.iter, ast.Call) and getattr(node.iter.func, "attr", "") == "all" for node in ast.walk(tree))


def test_product_service_keeps_sql_filtering_out_of_gui():
    service = (ROOT / "app" / "services" / "product_service.py").read_text(encoding="utf-8")
    page = (ROOT / "app" / "widgets" / "products_page.py").read_text(encoding="utf-8")
    assert "_build_product_query" in service
    assert "ilike" in service
    assert "cast(Product.id, String)" in service
    assert "PRODUCT_SORT_FIELDS" in service
    assert "select(Product)" not in page
    assert "session." not in page


def test_product_service_filter_spec_is_separate_and_typed():
    spec = (ROOT / "app" / "services" / "product_filters.py").read_text(encoding="utf-8")
    assert "@dataclass(frozen=True, slots=True)" in spec
    assert "PRODUCT_SORT_FIELDS" in spec
    assert "STOCK_FILTERS" in spec
    assert "has_filters" in spec


def test_product_images_are_exposed_in_dialog_catalogue_and_purchase_flow():
    page = (ROOT / "app" / "widgets" / "products_page.py").read_text(encoding="utf-8")
    transactions = (ROOT / "app" / "widgets" / "transaction_pages.py").read_text(encoding="utf-8")
    image_widgets = (ROOT / "app" / "widgets" / "product_image_widgets.py").read_text(encoding="utf-8")
    for token in ("Seleccionar imagen", "Ver imagen", "Quitar imagen", "Imagen del producto", "image_data", "ProductImageDialog", "product_pixmap"):
        assert token in page
    assert '"Foto", "ID", "SKU"' in page
    assert "create_product_from_purchase" in transactions
    assert "+ Nuevo producto" in transactions
    assert "product_image_button" in transactions
    assert "preserving aspect ratio" in image_widgets
