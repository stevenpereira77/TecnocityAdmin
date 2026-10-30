from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

MONEY = Numeric(18, 2, asdecimal=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="General")
    brand: Mapped[str] = mapped_column(String(100), default="")
    image_path: Mapped[str] = mapped_column(String(500), default="")
    # Small thumbnails are loaded by catalogue lists; full photos are deferred until opened.
    # Both live in SQLite so normal database backups include product images.
    image_thumbnail_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    image_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True, deferred=True)
    sale_price: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    stock_min: Mapped[int] = mapped_column(Integer, default=0)
    stock_current: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    purchase_items: Mapped[list["PurchaseItem"]] = relationship(back_populates="product")
    sale_items: Mapped[list["SaleItem"]] = relationship(back_populates="product")
    layers: Mapped[list["InventoryLayer"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    movements: Mapped[list["InventoryMovement"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    supplier: Mapped[str] = mapped_column(String(160), default="")
    shipping_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    other_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list["PurchaseItem"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    line_total: Mapped[Decimal] = mapped_column(MONEY)
    purchase: Mapped[Purchase] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="purchase_items")


class InventoryLayer(Base):
    __tablename__ = "inventory_layers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    purchase_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchase_items.id"), index=True, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    original_quantity: Mapped[int] = mapped_column(Integer)
    remaining_quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    product: Mapped[Product] = relationship(back_populates="layers")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    document_type: Mapped[str] = mapped_column(String(40), default="")
    document_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reason: Mapped[str] = mapped_column(String(200), default="")
    user_name: Mapped[str] = mapped_column(String(120), default="admin")
    notes: Mapped[str] = mapped_column(Text, default="")
    product: Mapped[Product] = relationship(back_populates="movements")


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    sale_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    # shipping_cost = costo real para Tecnocity. shipping_charge = cobro al cliente.
    shipping_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    shipping_charge: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    shipping_payer: Mapped[str] = mapped_column(String(30), default="TIENDA", index=True)
    shipping_refunded: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    other_cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    commission: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    payment_method: Mapped[str] = mapped_column(String(60), default="Efectivo")
    subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cogs: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    gross_profit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    net_profit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    # Snapshots inmutables de la operación original para auditoría y trazabilidad.
    original_subtotal: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    original_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    original_cogs: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    original_gross_profit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    original_net_profit: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))

    status: Mapped[str] = mapped_column("sale_status", String(30), default="CONFIRMADA", index=True)
    delivery_status: Mapped[str] = mapped_column(String(30), default="PENDIENTE", index=True)
    customer_name: Mapped[str] = mapped_column(String(160), default="")
    customer_phone: Mapped[str] = mapped_column(String(60), default="")
    customer_address: Mapped[str] = mapped_column(String(300), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancellation_reason: Mapped[str] = mapped_column(String(250), default="")
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["SaleItem"]] = relationship(back_populates="sale", cascade="all, delete-orphan")
    returns: Mapped[list["SaleReturn"]] = relationship(back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku_snapshot: Mapped[str] = mapped_column(String(60), default="")
    product_name_snapshot: Mapped[str] = mapped_column(String(160), default="")
    quantity: Mapped[int] = mapped_column(Integer)
    returned_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_sale_price: Mapped[Decimal] = mapped_column(MONEY)
    discount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    line_total: Mapped[Decimal] = mapped_column(MONEY)
    cogs: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="sale_items")
    allocations: Mapped[list["SaleLayerAllocation"]] = relationship(back_populates="sale_item", cascade="all, delete-orphan")


class SaleLayerAllocation(Base):
    __tablename__ = "sale_layer_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id"), index=True)
    inventory_layer_id: Mapped[int] = mapped_column(ForeignKey("inventory_layers.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    returned_quantity: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[Decimal] = mapped_column(MONEY)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    sale_item: Mapped[SaleItem] = relationship(back_populates="allocations")


class SaleReturn(Base):
    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    return_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    reason: Mapped[str] = mapped_column(String(250), default="")
    products_refunded: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    discount_refunded: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    shipping_refunded: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    total_refunded: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cogs_returned: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    profit_impact: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    notes: Mapped[str] = mapped_column(Text, default="")
    sale: Mapped[Sale] = relationship(back_populates="returns")
    items: Mapped[list["SaleReturnItem"]] = relationship(back_populates="sale_return", cascade="all, delete-orphan")


class SaleReturnItem(Base):
    __tablename__ = "sale_return_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_return_id: Mapped[int] = mapped_column(ForeignKey("sale_returns.id"), index=True)
    sale_item_id: Mapped[int] = mapped_column(ForeignKey("sale_items.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    product_refund: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    cogs_returned: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0.00"))
    sale_return: Mapped[SaleReturn] = relationship(back_populates="items")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    sale_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sales.id"), nullable=True, index=True)
    direct_sale: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    user_name: Mapped[str] = mapped_column(String(120), default="admin")
    details: Mapped[str] = mapped_column(Text, default="")
