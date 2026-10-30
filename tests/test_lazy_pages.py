from __future__ import annotations

import importlib.util

import pytest


def test_lazy_page_host_does_not_instantiate_factory_until_requested(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no está instalado en el entorno de validación.")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    from app.widgets.lazy_page import LazyPageHost

    app = QApplication.instance() or QApplication([])
    calls = []

    def factory():
        calls.append(True)
        return QLabel("loaded")

    host = LazyPageHost(factory, "Prueba")
    assert calls == []
    assert not host.is_loaded
    host.ensure_loaded()
    assert calls == [True]
    assert host.is_loaded
    host.ensure_loaded()
    assert calls == [True]
    host.deleteLater()
    app.processEvents()
