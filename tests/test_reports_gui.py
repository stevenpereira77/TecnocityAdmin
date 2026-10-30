import ast
from pathlib import Path
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_reports_page_has_professional_report_controls():
    source = (ROOT / "app" / "widgets" / "reports_page.py").read_text(encoding="utf-8")
    for token in (
        "Centro de reportes", "Exportar Excel", "Exportar CSV", "Generar PDF", "Imprimir",
        "Vista previa", "Filtros del reporte", "Personalizado", "QTableView", "QSortFilterProxyModel",
        "ReportTableModel", "report_service.build",
    ):
        assert token in source
    assert "QMessageBox.critical" in source


def test_reports_page_does_not_calculate_financials_in_gui():
    source = (ROOT / "app" / "widgets" / "reports_page.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"Decimal", "float", "sum"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names.intersection(forbidden)


def test_report_table_model_is_separate_from_report_service():
    model_source = (ROOT / "app" / "reports" / "qt_model.py").read_text(encoding="utf-8")
    service_source = (ROOT / "app" / "reports" / "service.py").read_text(encoding="utf-8")
    assert "class ReportTableModel" in model_source
    assert "class ReportService" in service_source
    assert "PySide6" not in service_source


def test_main_window_registers_reports_page_lazily():
    source = (ROOT / "app" / "views" / "main_window.py").read_text(encoding="utf-8")
    assert '"Reportes"' in source
    assert "def _reports_factory" in source
    assert "return ReportsPage(" in source
    assert "LazyPageHost" in source


def test_reports_page_constructs_when_qt_is_available(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no está instalado en el entorno de validación.")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDateEdit, QTableView
    from app.reports.service import ReportService
    from app.widgets.reports_page import ReportsPage
    from app.database import create_database_engine, create_session_factory, initialize_database
    from pathlib import Path

    app = QApplication.instance() or QApplication([])
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    service = ReportService(create_session_factory(engine))
    page = ReportsPage(service, Path("/tmp/tecnocity-test-exports"))
    assert page.report_combo.count() == 8
    assert page.period_combo.count() == 9
    assert page.table.isSortingEnabled()
    assert isinstance(page.table, QTableView)
    assert isinstance(page.start_edit, QDateEdit)
    assert not page.start_edit.isVisible()
    page.deleteLater()
    app.processEvents()


def test_print_service_does_not_import_business_services():
    source = (ROOT / "app" / "reports" / "print_service.py").read_text(encoding="utf-8")
    assert "app.services" not in source
    assert "QPrintDialog" in source
    assert "QTextDocument" in source
    assert "report_html(result, rows)" in source
