from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.theme import ThemeManager


class AppearanceSection(QWidget):
    """Self-contained appearance settings so the configuration page can grow by modules."""

    theme_applied = Signal(str)

    def __init__(self, theme_manager: ThemeManager) -> None:
        super().__init__()
        self.theme_manager = theme_manager
        self._saved_key = theme_manager.current_key()
        self._build_ui()
        self._load_from_store()

    def _build_ui(self) -> None:
        self.setObjectName("themeSettings")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        eyebrow = QLabel("APARIENCIA")
        eyebrow.setObjectName("themeSettingsEyebrow")
        root.addWidget(eyebrow)

        title = QLabel("Personaliza la experiencia de Tecnocity")
        title.setObjectName("themeSettingsTitle")
        root.addWidget(title)

        hint = QLabel("Elige un tema. El cambio se aplica a toda la aplicación y queda guardado automáticamente al pulsar Aplicar tema.")
        hint.setObjectName("themeSettingsHint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        self.theme_selector = QComboBox()
        self.theme_selector.setObjectName("themeSelector")
        for theme in self.theme_manager.available_themes():
            self.theme_selector.addItem(theme.label, theme.key)
        self.theme_selector.currentIndexChanged.connect(self._selection_changed)
        selector_row.addWidget(self.theme_selector, 1)

        self.status = QLabel()
        self.status.setObjectName("themeStatus")
        selector_row.addWidget(self.status)
        root.addLayout(selector_row)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)
        self._cards: dict[str, QWidget] = {}
        for index, theme in enumerate(self.theme_manager.available_themes()):
            card = self._build_theme_card(theme.key, theme.label, theme.description, theme.accent)
            self._cards[theme.key] = card
            cards.addWidget(card, 0, index)
        root.addLayout(cards)

        preview = QFrame()
        preview.setObjectName("themePreviewCard")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(16, 14, 16, 14)
        preview_layout.setSpacing(8)

        preview_header = QHBoxLayout()
        accent_bar = QFrame()
        accent_bar.setObjectName("themePreviewAccentBar")
        preview_header.addWidget(accent_bar, 1)
        self.preview_badge = QLabel("PREVISUALIZACIÓN")
        self.preview_badge.setObjectName("themePreviewBadge")
        preview_header.addWidget(self.preview_badge, 0)
        preview_layout.addLayout(preview_header)

        self.preview_title = QLabel("Dashboard ejecutivo")
        self.preview_title.setObjectName("themePreviewTitle")
        preview_layout.addWidget(self.preview_title)
        self.preview_metric = QLabel("$ 4.850.000")
        self.preview_metric.setObjectName("themePreviewMetric")
        preview_layout.addWidget(self.preview_metric)
        self.preview_metric_label = QLabel("Ventas netas · período seleccionado")
        self.preview_metric_label.setObjectName("themePreviewMetricLabel")
        preview_layout.addWidget(self.preview_metric_label)
        self.preview_text = QLabel()
        self.preview_text.setObjectName("themePreviewText")
        self.preview_text.setWordWrap(True)
        preview_layout.addWidget(self.preview_text)
        root.addWidget(preview)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        apply_button = QPushButton("Aplicar tema")
        apply_button.setObjectName("applyThemeButton")
        apply_button.clicked.connect(self._apply)
        buttons.addWidget(apply_button)
        reset = QPushButton("Restablecer modo claro")
        reset.setObjectName("resetThemeButton")
        reset.clicked.connect(self._reset)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        root.addLayout(buttons)

        footer = QLabel("Preferencia guardada localmente en la configuración del usuario.")
        footer.setObjectName("themeFooter")
        root.addWidget(footer)

    def _build_theme_card(self, key: str, label: str, description: str, accent: str) -> QWidget:
        card = QWidget()
        card.setObjectName("themeCard")
        card.setProperty("theme_key", key)
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 9, 10, 9)
        layout.setSpacing(8)

        swatch = QLabel()
        swatch.setObjectName("themeCardSwatch")
        swatch.setProperty("theme_accent", accent)
        # The preview swatch intentionally keeps the palette accent for each
        # card; the actual application theme never depends on inline styles.
        swatch.setStyleSheet(f"background: {accent}; border: 1px solid {accent};")
        layout.addWidget(swatch)

        text_wrap = QVBoxLayout()
        text_wrap.setSpacing(2)
        name = QLabel(label)
        name.setObjectName("themeCardName")
        desc = QLabel(description)
        desc.setObjectName("themeCardDescription")
        desc.setWordWrap(True)
        text_wrap.addWidget(name)
        text_wrap.addWidget(desc)
        layout.addLayout(text_wrap, 1)

        button = QPushButton("Elegir")
        button.setObjectName("themeCardButton")
        button.clicked.connect(lambda _checked=False, k=key: self._select_key(k))
        layout.addWidget(button)
        return card

    def _load_from_store(self) -> None:
        self._select_key(self._saved_key, mark_unsaved=False)

    def _select_key(self, key: str, *, mark_unsaved: bool = True) -> None:
        theme = self.theme_manager.get_theme(key)
        index = self.theme_selector.findData(theme.key)
        if index >= 0 and self.theme_selector.currentIndex() != index:
            self.theme_selector.blockSignals(True)
            self.theme_selector.setCurrentIndex(index)
            self.theme_selector.blockSignals(False)
        self._update_preview(theme.key)
        if mark_unsaved:
            self._update_status(theme.key != self._saved_key)

    def _selection_changed(self) -> None:
        key = str(self.theme_selector.currentData() or "light")
        self._update_preview(key)
        self._update_status(key != self._saved_key)

    def _update_preview(self, key: str) -> None:
        theme = self.theme_manager.get_theme(key)
        self.preview_text.setText(theme.description)
        for theme_key, card in self._cards.items():
            card.setProperty("selected", theme_key == theme.key)
            card.style().unpolish(card)
            card.style().polish(card)

    def _update_status(self, unsaved: bool) -> None:
        if unsaved:
            self.status.setProperty("state", "unsaved")
            self.status.setText("● Cambios sin guardar")
        else:
            self.status.setProperty("state", "saved")
            self.status.setText("● Guardado")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _apply(self) -> None:
        key = str(self.theme_selector.currentData() or "light")
        try:
            self.theme_manager.save_theme(key)
        except (OSError, ValueError) as exc:
            self.status.setProperty("state", "error")
            self.status.setText("● No se pudo guardar")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        self._saved_key = key
        self._update_status(False)
        self.theme_applied.emit(key)

    def _reset(self) -> None:
        self._select_key("light")
        self._apply()

    def refresh(self) -> None:
        saved = self.theme_manager.current_key()
        self._saved_key = saved
        self._select_key(saved, mark_unsaved=False)
        self._update_status(False)
