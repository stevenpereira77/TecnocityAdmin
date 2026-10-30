from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.backups import BackupManager
from app.config import AppSettings, SettingsStore
from app.services import StoreService
from app.theme import ThemeManager
from app.widgets.lazy_page import LazyPageHost


class MainWindow(QMainWindow):
    """Application shell with lazy pages and targeted refreshes.

    Only the Dashboard is created during startup. Other pages are lightweight
    hosts until the user opens them, preventing hidden pages from performing
    expensive database reads on every application launch or navigation event.
    """

    def __init__(
        self,
        settings: AppSettings,
        service: StoreService,
        settings_store: SettingsStore | None = None,
        backup_manager: BackupManager | None = None,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.service = service
        self.settings_store = settings_store or SettingsStore(settings.user_settings_path)
        self.backup_manager = backup_manager
        self.theme_manager = ThemeManager(settings.project_root, self.settings_store)
        self.setMinimumSize(1240, 760)
        self.resize(1420, 900)
        self.setWindowTitle(f"{settings.app_name} · v{settings.version}")
        self._build_ui()
        self._apply_styles()
        self._configure_startup_backup()
        # Let the shell render before the initial Dashboard does its first query.
        QTimer.singleShot(0, lambda: self._navigate(0, refresh=True))

    def _page_factories(self):
        factories = [
            ("Dashboard", self._dashboard_factory),
            ("Productos", self._products_factory),
            ("Inventario", self._inventory_factory),
            ("Compras", self._purchases_factory),
            ("Ventas", self._sales_factory),
            ("Gastos", self._expenses_factory),
            ("Reportes", self._reports_factory),
            ("Auditoría", self._audit_factory),
        ]
        if self.backup_manager is not None:
            factories.append(("Configuración", self._settings_page_factory))
        return factories

    def _dashboard_factory(self):
        from app.widgets.dashboard_page import DashboardPage
        return DashboardPage(self.service)

    def _products_factory(self):
        from app.widgets.products_page import ProductsPage
        return ProductsPage(self.service)

    def _inventory_factory(self):
        from app.widgets.inventory_page import InventoryPage
        return InventoryPage(self.service)

    def _purchases_factory(self):
        from app.widgets.transaction_pages import PurchasesPage
        return PurchasesPage(self.service)

    def _sales_factory(self):
        from app.widgets.transaction_pages import SalesPage
        return SalesPage(self.service)

    def _expenses_factory(self):
        from app.widgets.expenses_page import ExpensesPage
        return ExpensesPage(self.service)

    def _reports_factory(self):
        from app.widgets.reports_page import ReportsPage
        return ReportsPage(self.service.report_service, self.settings.data_dir)

    def _audit_factory(self):
        from app.widgets.audit_page import AuditPage
        return AuditPage(self.service)

    def _settings_page_factory(self):
        from app.widgets.settings_page import SettingsPage
        return SettingsPage(self.settings, self.settings_store, self.backup_manager, self.theme_manager)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(244)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 24, 18, 18)
        side_layout.setSpacing(6)

        brand = QLabel("TECNOCITY")
        brand.setObjectName("brand")
        side_layout.addWidget(brand)
        subtitle = QLabel(f"ADMIN · v{self.settings.version}")
        subtitle.setObjectName("brandSubtitle")
        side_layout.addWidget(subtitle)
        side_layout.addSpacing(18)

        self.stack = QStackedWidget()
        factories = self._page_factories()
        self.pages: dict[str, LazyPageHost] = {}
        self.page_names: list[str] = []
        for name, factory in factories:
            host = LazyPageHost(factory, name)
            self.pages[name] = host
            self.page_names.append(name)
            self.stack.addWidget(host)

        self.nav_buttons = []
        for index, name in enumerate(self.page_names):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, i=index: self._navigate(i, refresh=True))
            side_layout.addWidget(button)
            self.nav_buttons.append(button)
        self.nav_buttons[0].setChecked(True)
        side_layout.addStretch(1)
        pending = QLabel(
            f"v{self.settings.version} · servicios por dominio\n\n"
            "Carga bajo demanda para bases grandes.\n"
            "Reportes, exportación y configuración profesional integrados."
        )
        pending.setObjectName("stageLabel")
        pending.setWordWrap(True)
        side_layout.addWidget(pending)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _navigate(self, index: int, refresh: bool = True) -> None:
        if not (0 <= index < len(self.page_names)):
            return
        self.stack.setCurrentIndex(index)
        page = self.pages[self.page_names[index]]
        was_loaded = page.is_loaded
        page.ensure_loaded()
        # Each page performs its first load in its constructor. Avoid duplicating
        # that query; subsequent visits get a normal targeted refresh.
        if refresh and was_loaded:
            page.refresh()
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)

    def refresh_current_page(self) -> None:
        index = self.stack.currentIndex()
        if 0 <= index < len(self.page_names):
            self.pages[self.page_names[index]].refresh()

    def refresh_all(self) -> None:
        """Compatibility method: refresh only pages already instantiated.

        It deliberately does not create hidden pages. This preserves older callers
        while removing the cross-module refresh storm that previously happened on
        every navigation event.
        """
        for page in self.pages.values():
            if page.is_loaded:
                page.refresh()
                page.refresh_products()
                page.refresh_history()

    def _configure_startup_backup(self) -> None:
        if self.backup_manager is None:
            return
        backup = self.settings_store.section("backup")
        if not backup.get("backup_on_startup"):
            return
        QTimer.singleShot(2500, self._backup_on_startup)

    def _backup_on_startup(self) -> None:
        if self.backup_manager is None:
            return
        today = datetime.now().date().isoformat()
        recent = self.backup_manager.history.list(limit=20)
        already = any(
            str(entry.get("created_at", "")).startswith(today)
            and str(entry.get("status", "")) == "SUCCESS"
            for entry in recent
        )
        if not already:
            self.backup_manager.backup_now(reason="startup")
            settings_page = self.pages.get("Configuración")
            if settings_page is not None and settings_page.is_loaded:
                settings_page.refresh()

    def _apply_styles(self) -> None:
        self.apply_theme(self.theme_manager.current_key())

    def apply_theme(self, key: str | None = None) -> None:
        theme = self.theme_manager.get_theme(key or self.theme_manager.current_key())
        qapp = self._qapplication()
        if qapp is not None:
            qapp.setProperty("tecnocityTheme", theme.key)
            qapp.setStyleSheet(self.theme_manager.stylesheet(theme.key))
            qapp.setPalette(self.theme_manager.qt_palette(theme.key))
        else:
            self.setStyleSheet(self.theme_manager.stylesheet(theme.key))
        for page in self.pages.values():
            page.on_theme_changed(theme)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    @staticmethod
    def _qapplication():
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()
