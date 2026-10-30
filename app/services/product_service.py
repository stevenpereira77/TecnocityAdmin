"""Catalog/product business operations and advanced catalogue queries."""
from __future__ import annotations

from sqlalchemy import String, asc, cast, desc, func, select
from sqlalchemy.orm import undefer

from app.calculations.financial import money
from app.core.exceptions import ValidationError
from app.models import Product
from app.utils.product_images import validate_product_image_data
from app.services.base_service import BaseService
from app.services.product_filters import PRODUCT_SORT_FIELDS, ProductFilter


class ProductService(BaseService):
    """Create, query, filter, update and activate/deactivate products.

    Query construction stays in the service layer so the GUI never needs to
    know SQLAlchemy details. ``ProductFilter`` is reusable by future reports,
    API endpoints or other screens.
    """

    def list_products(
        self,
        search: str = "",
        active_only: bool = False,
        filters: ProductFilter | None = None,
    ) -> list[Product]:
        if filters is None:
            filters = ProductFilter(search=search, active=True if active_only else None, sort_by="name", sort_direction="asc")
        with self._session() as session:
            stmt = self._build_product_query(filters)
            return list(session.scalars(stmt).all())

    def count_products(self, filters: ProductFilter | None = None) -> int:
        filters = filters or ProductFilter()
        with self._session() as session:
            stmt = self._build_product_query(filters, columns_only=True)
            return int(session.scalar(stmt) or 0)

    def list_products_page(self, filters: ProductFilter | None = None, *, page: int = 1, page_size: int = 100) -> tuple[list[Product], int]:
        """Return one bounded page plus the total matching row count."""
        filters = filters or ProductFilter()
        page = max(1, int(page))
        page_size = max(25, min(int(page_size), 500))
        with self._session() as session:
            stmt = self._build_product_query(filters).limit(page_size).offset((page - 1) * page_size)
            rows = list(session.scalars(stmt).all())
            total = int(session.scalar(self._build_product_query(filters, columns_only=True)) or 0)
            return rows, total

    def filter_options(self) -> dict[str, list[str]]:
        """Return distinct category/brand options for filter controls."""
        with self._session() as session:
            categories = list(
                session.scalars(
                    select(Product.category)
                    .where(func.trim(Product.category) != "")
                    .distinct()
                    .order_by(Product.category.asc())
                ).all()
            )
            brands = list(
                session.scalars(
                    select(Product.brand)
                    .where(func.trim(Product.brand) != "")
                    .distinct()
                    .order_by(Product.brand.asc())
                ).all()
            )
            return {"categories": categories, "brands": brands}

    @staticmethod
    def _build_product_query(filters: ProductFilter, columns_only: bool = False):
        if columns_only:
            stmt = select(func.count(Product.id))
        else:
            stmt = select(Product)

        if filters.search:
            q = f"%{filters.search}%"
            stmt = stmt.where(
                (cast(Product.id, String).ilike(q))
                | (Product.name.ilike(q))
                | (Product.sku.ilike(q))
                | (Product.category.ilike(q))
                | (Product.brand.ilike(q))
                | (Product.description.ilike(q))
            )
        if filters.product_id is not None:
            stmt = stmt.where(Product.id == filters.product_id)
        if filters.id_min is not None:
            stmt = stmt.where(Product.id >= filters.id_min)
        if filters.id_max is not None:
            stmt = stmt.where(Product.id <= filters.id_max)
        if filters.category:
            stmt = stmt.where(Product.category == filters.category)
        if filters.brand:
            stmt = stmt.where(Product.brand == filters.brand)
        if filters.active is not None:
            stmt = stmt.where(Product.active.is_(filters.active))
        if filters.stock_status == "in_stock":
            stmt = stmt.where(Product.stock_current > 0)
        elif filters.stock_status == "low":
            stmt = stmt.where(Product.stock_current > 0, Product.stock_current <= Product.stock_min)
        elif filters.stock_status == "out":
            stmt = stmt.where(Product.stock_current == 0)
        if filters.price_min is not None:
            stmt = stmt.where(Product.sale_price >= money(filters.price_min))
        if filters.price_max is not None:
            stmt = stmt.where(Product.sale_price <= money(filters.price_max))
        if filters.created_from is not None:
            stmt = stmt.where(Product.created_at >= filters.created_from)
        if filters.created_to is not None:
            stmt = stmt.where(Product.created_at <= filters.created_to)

        if not columns_only:
            sort_column = getattr(Product, PRODUCT_SORT_FIELDS[filters.sort_by])
            direction = desc if filters.sort_direction == "desc" else asc
            # Stable secondary key prevents visual reordering when values tie.
            if filters.sort_by == "id":
                stmt = stmt.order_by(direction(sort_column))
            else:
                stmt = stmt.order_by(direction(sort_column), Product.id.asc())
        return stmt

    def create_product(
        self,
        *,
        sku: str,
        name: str,
        sale_price,
        stock_min: int = 0,
        category: str = "General",
        brand: str = "",
        description: str = "",
        image_path: str = "",
        image_data: bytes | None = None,
        image_thumbnail_data: bytes | None = None,
    ) -> Product:
        sku = sku.strip().upper()
        name = name.strip()
        if not sku or not name:
            raise ValidationError("SKU y nombre son obligatorios.")
        if int(stock_min) < 0:
            raise ValidationError("El stock mínimo no puede ser negativo.")
        price = money(sale_price)
        if price < 0:
            raise ValidationError("El precio de venta no puede ser negativo.")
        try:
            stored_image_data = validate_product_image_data(image_data)
            stored_thumbnail_data = validate_product_image_data(image_thumbnail_data)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        cleaned_image_path = "" if stored_image_data else str(image_path or "").strip()

        with self._session() as session:
            if session.scalar(select(Product).where(Product.sku == sku)):
                raise ValidationError(f"El SKU '{sku}' ya existe.")
            product = Product(
                sku=sku,
                name=name,
                category=(category or "General").strip(),
                brand=brand.strip(),
                description=description.strip(),
                image_path=cleaned_image_path,
                image_data=stored_image_data,
                image_thumbnail_data=stored_thumbnail_data,
                sale_price=price,
                stock_min=int(stock_min),
            )
            session.add(product)
            session.flush()
            self._audit(session, "CREAR", "PRODUCTO", product.id, f"SKU={product.sku}; nombre={product.name}")
            session.commit()
            session.refresh(product)
            return product

    def update_product(self, product_id: int, **data) -> Product:
        with self._session() as session:
            product = session.get(Product, int(product_id))
            if not product:
                raise ValidationError("Producto no encontrado.")

            if "sku" in data:
                sku = str(data["sku"]).strip().upper()
                if not sku:
                    raise ValidationError("El SKU es obligatorio.")
                exists = session.scalar(select(Product).where(Product.sku == sku, Product.id != product.id))
                if exists:
                    raise ValidationError(f"El SKU '{sku}' ya existe.")
                product.sku = sku

            if "name" in data:
                product.name = str(data["name"]).strip()
            if not product.name:
                raise ValidationError("El nombre del producto es obligatorio.")

            if "sale_price" in data:
                price = money(data["sale_price"])
                if price < 0:
                    raise ValidationError("El precio de venta no puede ser negativo.")
                product.sale_price = price

            if "stock_min" in data:
                product.stock_min = max(0, int(data["stock_min"]))

            for key in ("category", "brand", "description", "image_path"):
                if key in data:
                    setattr(product, key, str(data[key] or "").strip())

            if "image_data" in data:
                try:
                    product.image_data = validate_product_image_data(data["image_data"])
                    product.image_thumbnail_data = validate_product_image_data(data.get("image_thumbnail_data"))
                except ValueError as exc:
                    raise ValidationError(str(exc)) from exc
                # The new database image takes precedence over legacy path images.
                if product.image_data:
                    product.image_path = ""

            self._audit(session, "ACTUALIZAR", "PRODUCTO", product.id, f"SKU={product.sku}; nombre={product.name}")
            session.commit()
            session.refresh(product)
            return product

    def toggle_product(self, product_id: int) -> None:
        with self._session() as session:
            product = session.get(Product, int(product_id))
            if not product:
                raise ValidationError("Producto no encontrado.")
            product.active = not product.active
            self._audit(session, "CAMBIAR_ESTADO", "PRODUCTO", product.id, f"activo={product.active}")
            session.commit()

    def get_product(self, product_id: int) -> Product | None:
        """Fetch one product including its full image for detail/preview screens."""
        with self._session() as session:
            return session.scalar(
                select(Product)
                .options(undefer(Product.image_data))
                .where(Product.id == int(product_id))
            )
