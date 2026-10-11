"""
Gerenciador de Temas do QDir Linux.
Carrega e sincroniza configurações do Qt6 (qt6ct / Qt6 Settings, Breeze, Kvantum, etc.),
garantindo aplicação correta de temas escuros, paletas, fontes e ícones do sistema.
"""

import configparser
import os
import sys
from typing import Optional

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory


def setup_qt_environment():
    """Configura caminhos de bibliotecas e plugins Qt antes da inicialização do QApplication."""
    # Adiciona diretórios de plugins do sistema
    plugin_paths = [
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt6/plugins",
        "/usr/local/lib/qt6/plugins",
    ]
    for p in plugin_paths:
        if os.path.isdir(p):
            QCoreApplication.addLibraryPath(p)

    # Se QT_STYLE_OVERRIDE estiver apontando para um estilo incompatível na sessão
    # (como kvantum sem libstdc++ com CXXABI_1.3.15 no ambiente conda),
    # removemos para evitar avisos no terminal e permitir que o tema do qt6ct assuma.
    style_override = os.environ.get("QT_STYLE_OVERRIDE", "")
    if style_override:
        # Se for kvantum e a biblioteca do kvantum falhar ou não estiver pronta,
        # limpamos temporariamente
        available_styles = [s.lower() for s in QStyleFactory.keys()]
        if style_override.lower() not in available_styles:
            os.environ.pop("QT_STYLE_OVERRIDE", None)


def _parse_qt6ct_palette(color_scheme_path: str, app: QApplication) -> Optional[QPalette]:
    """Lê um arquivo de esquema de cores do qt6ct e cria a QPalette correspondente."""
    if not color_scheme_path or not os.path.isfile(color_scheme_path):
        return None

    scheme_cp = configparser.ConfigParser()
    try:
        scheme_cp.read(color_scheme_path)
    except Exception:
        return None

    if "ColorScheme" not in scheme_cp:
        return None

    # Mapeamento canônico das 21 cores do qt6ct para QPalette.ColorRole
    roles = [
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Button,
        QPalette.ColorRole.Light,
        QPalette.ColorRole.Midlight,
        QPalette.ColorRole.Dark,
        QPalette.ColorRole.Mid,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.BrightText,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.Base,
        QPalette.ColorRole.Window,
        QPalette.ColorRole.Shadow,
        QPalette.ColorRole.Highlight,
        QPalette.ColorRole.HighlightedText,
        QPalette.ColorRole.Link,
        QPalette.ColorRole.LinkVisited,
        QPalette.ColorRole.AlternateBase,
        QPalette.ColorRole.NoRole,
        QPalette.ColorRole.ToolTipBase,
        QPalette.ColorRole.ToolTipText,
        QPalette.ColorRole.PlaceholderText,
    ]

    pal = QPalette(app.palette())
    groups = [
        ("active_colors", QPalette.ColorGroup.Active),
        ("disabled_colors", QPalette.ColorGroup.Disabled),
        ("inactive_colors", QPalette.ColorGroup.Inactive),
    ]

    has_colors = False
    for group_key, group in groups:
        raw_colors = scheme_cp.get("ColorScheme", group_key, fallback="")
        if raw_colors:
            colors = [c.strip() for c in raw_colors.split(",") if c.strip()]
            for r_idx, color_hex in enumerate(colors):
                if r_idx < len(roles):
                    pal.setColor(group, roles[r_idx], QColor(color_hex))
                    has_colors = True

    return pal if has_colors else None


def apply_system_theme(app: QApplication) -> bool:
    """
    Detecta e aplica o tema configurado no Qt6 Settings (qt6ct), KDE ou sistema.
    Retorna True se configurações personalizadas foram aplicadas.
    """
    # 1. Tenta carregar do qt6ct (~/.config/qt6ct/qt6ct.conf)
    conf_path = os.path.expanduser("~/.config/qt6ct/qt6ct.conf")
    applied = False

    if os.path.isfile(conf_path):
        cp = configparser.ConfigParser()
        try:
            cp.read(conf_path)

            # A. Estilo de Interface (Breeze, Fusion, etc.)
            style_name = cp.get("Appearance", "style", fallback="").strip()
            if style_name:
                available = QStyleFactory.keys()
                matched = next((s for s in available if s.lower() == style_name.lower()), None)
                if matched:
                    app.setStyle(matched)
                elif "Fusion" in available:
                    app.setStyle("Fusion")

            # B. Paleta de Cores (ex: darker.conf)
            custom_palette = cp.getboolean("Appearance", "custom_palette", fallback=True)
            color_scheme = cp.get("Appearance", "color_scheme_path", fallback="").strip()
            if custom_palette and color_scheme:
                color_scheme = os.path.expanduser(os.path.expandvars(color_scheme))
                pal = _parse_qt6ct_palette(color_scheme, app)
                if pal:
                    app.setPalette(pal)
                    applied = True

            # C. Fontes
            font_str = cp.get("Fonts", "general", fallback="").strip().strip("\"'")
            if font_str:
                font = QFont()
                if font.fromString(font_str):
                    app.setFont(font)

            # D. Tema de Ícones
            icon_theme = cp.get("Appearance", "icon_theme", fallback="").strip().strip("\"'")
            if icon_theme:
                QIcon.setThemeName(icon_theme)

        except Exception as e:
            print(f"[QDir Theme] Erro ao processar qt6ct.conf: {e}", file=sys.stderr)

    # 2. Se nenhuma paleta personalizada foi aplicada, verifica modo escuro no sistema como fallback
    if not applied:
        is_dark = False
        try:
            import subprocess

            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if "dark" in res.stdout.lower():
                is_dark = True
        except Exception:
            pass

        if is_dark:
            app.setStyle("Fusion")
            dark_pal = QPalette()
            dark_pal.setColor(QPalette.ColorRole.Window, QColor(34, 32, 32))
            dark_pal.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
            dark_pal.setColor(QPalette.ColorRole.Base, QColor(48, 48, 48))
            dark_pal.setColor(QPalette.ColorRole.AlternateBase, QColor(40, 40, 40))
            dark_pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
            dark_pal.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
            dark_pal.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
            dark_pal.setColor(QPalette.ColorRole.Button, QColor(45, 45, 48))
            dark_pal.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
            dark_pal.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
            dark_pal.setColor(QPalette.ColorRole.Highlight, QColor(18, 96, 138))
            dark_pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
            app.setPalette(dark_pal)
            applied = True

    return applied
