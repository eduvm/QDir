"""
Testes automatizados para o tema dinâmico do Wallpaper (Pywal + OpenRGB) e hot-reload no QDir.
"""

import json
import os
import sys

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication

from qdir.theme_manager import (
    WallpaperThemeWatcher,
    _build_pywal_palette,
    apply_system_theme,
    setup_qt_environment,
)


def _get_app():
    setup_qt_environment()
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_build_pywal_palette_and_hot_reload(monkeypatch, tmp_path):
    app = _get_app()

    # Cria estrutura simulada de cache XDG para Pywal e OpenRGB (cw)
    wal_dir = tmp_path / "wal"
    cw_dir = tmp_path / "cw"
    wal_dir.mkdir()
    cw_dir.mkdir()

    wal_json = wal_dir / "colors.json"
    rgb_state = cw_dir / "last-rgb"

    wal_data = {
        "special": {
            "background": "#0D1413",
            "foreground": "#a0dae0",
            "cursor": "#a0dae0",
        },
        "colors": {
            "color0": "#0D1413",
            "color1": "#9E6667",
            "color5": "#2999A4",
        },
    }
    wal_json.write_text(json.dumps(wal_data), encoding="utf-8")
    rgb_state.write_text("00AFBF\n", encoding="utf-8")

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    pal = _build_pywal_palette(app)
    assert pal is not None
    assert pal.color(QPalette.ColorRole.Base).name().lower() == "#0d1413"
    hl_1 = pal.color(QPalette.ColorRole.Highlight).name().lower()

    # Muda a cor do OpenRGB (simulando troca de wallpaper pelo cw.sh)
    rgb_state.write_text("FF5500\n", encoding="utf-8")
    pal2 = _build_pywal_palette(app)
    assert pal2 is not None
    hl_2 = pal2.color(QPalette.ColorRole.Highlight).name().lower()
    assert hl_1 != hl_2

    # Testa alternância entre Wallpaper (True) e qt6ct (False)
    apply_system_theme(app, use_wallpaper=True)
    assert app.palette().color(QPalette.ColorRole.Highlight).name().lower() == hl_2

    reloaded = []
    watcher = WallpaperThemeWatcher(app, on_theme_updated=lambda: reloaded.append(True))
    watcher.set_enabled(False)
    assert len(reloaded) == 1
    assert app.palette().color(QPalette.ColorRole.Highlight).name().lower() != hl_2

    watcher.set_enabled(True)
    assert len(reloaded) == 2
    assert app.palette().color(QPalette.ColorRole.Highlight).name().lower() == hl_2
