from __future__ import annotations
from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget
from app.services import StoreService
from .ui_helpers import add_row, add_table_columns, fmt_money, make_lineedit, make_money_edit, show_error, show_info

class ExpensesPage(QWidget):
    def __init__(self, service: StoreService):
        super().__init__(); self.service=service; self._build_ui(); self.refresh()
    def _build_ui(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(30,26,30,30); layout.setSpacing(14)
        t=QLabel("Gastos"); t.setObjectName("pageTitle"); s=QLabel("Separa gastos generales de gastos directamente relacionados con una venta."); s.setObjectName("pageSubtitle"); layout.addWidget(t); layout.addWidget(s)
        form=QFormLayout(); self.category=QComboBox(); self.category.addItems(["Envíos","Empaques","Publicidad","Comisiones","Transporte","Herramientas","Otros"]); self.description=make_lineedit("Descripción"); self.amount=make_money_edit(); self.direct=QComboBox(); self.direct.addItems(["General","Directo a una venta"]); self.sale=QComboBox(); self.notes=make_lineedit("Observación opcional"); self.direct.currentIndexChanged.connect(self._toggle_sale); form.addRow("Categoría",self.category); form.addRow("Descripción",self.description); form.addRow("Valor",self.amount); form.addRow("Tipo",self.direct); form.addRow("Venta relacionada",self.sale); form.addRow("Observación",self.notes); b=QPushButton("Registrar gasto"); b.setObjectName("primaryButton"); b.clicked.connect(self.save); form.addRow(b); layout.addLayout(form)
        label=QLabel("Gastos recientes"); label.setObjectName("sectionLabel"); layout.addWidget(label); self.table=QTableWidget(); add_table_columns(self.table,["Fecha","Categoría","Descripción","Valor","Tipo","Venta"]); layout.addWidget(self.table)
        self._toggle_sale()
    def _toggle_sale(self): self.sale.setEnabled(self.direct.currentIndex()==1)
    def refresh(self):
        self.table.setRowCount(0); self.sale.clear(); self.sale.addItem("Seleccione...",None)
        for s in self.service.sales(): self.sale.addItem(f"{s.number} · {fmt_money(s.total)}",s.id)
        for e in self.service.expenses(): add_row(self.table,[e.expense_date.strftime("%Y-%m-%d"),e.category,e.description,fmt_money(e.amount),"Directo" if e.direct_sale else "General",str(e.sale_id or "-")])
        self._toggle_sale()
    def save(self):
        try:
            direct=self.direct.currentIndex()==1; sale_id=self.sale.currentData() if direct else None
            expense=self.service.register_expense(category=self.category.currentText(),description=self.description.text(),amount=self._money(self.amount),direct_sale=direct,sale_id=sale_id,notes=self.notes.text()); show_info(self,f"Gasto registrado por {fmt_money(expense.amount)}."); self.description.clear(); self.amount.setText("0.00"); self.notes.clear(); self.refresh()
        except Exception as exc: show_error(self,str(exc))
    @staticmethod
    def _money(edit):
        text=edit.text().strip() or "0"; return text.replace(".","").replace(",",".") if "," in text else text
