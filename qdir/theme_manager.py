"""
Gerenciador de Temas do QDir Linux.
Carrega e sincroniza configurações do Qt6 (qt6ct / Qt6 Settings, Breeze, Kvantum, etc.)
e suporta paleta dinâmica sincronizada com o Wallpaper (Pywal + OpenRGB) com hot-reload.
"""

import configparser
import json
import os
import re
import sys
from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QCoreApplication, QFileSystemWatcher, QObject, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import QApplication, QStyleFactory

HEX_COLOR_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")
RGB = Tuple[int, int, int]

BASE_MENU_QSS = """
QMenuBar {
    background-color: transparent;
    color: palette(window-text);
}
QMenuBar::item {
    background: transparent;
    color: palette(window-text);
    padding: 4px 8px;
    margin: 1px 2px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QMenuBar::item:pressed {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QMenu {
    background-color: palette(window);
    color: palette(window-text);
    border: 1px solid rgba(128, 128, 128, 0.4);
    padding: 4px 0;
}
QMenu::item {
    padding: 4px 24px 4px 16px;
    color: palette(window-text);
}
QMenu::item:selected {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QMenu::separator {
    height: 1px;
    background: rgba(128, 128, 128, 0.3);
    margin: 4px 8px;
}
"""

WALLPAPER_EXTRA_QSS = """
QMainWindow, QDialog {
    background-color: palette(window);
    color: palette(window-text);
}
QToolBar {
    background-color: palette(window);
    border-bottom: 1px solid palette(mid);
    spacing: 4px;
}
QStatusBar {
    background-color: palette(window);
    color: palette(window-text);
}
QTableView, QTreeView {
    background-color: palette(base);
    alternate-background-color: palette(alternate-base);
    color: palette(text);
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
    gridline-color: rgba(128, 128, 128, 0.18);
}
QHeaderView::section {
    background-color: palette(button);
    color: palette(button-text);
    border: none;
    border-right: 1px solid rgba(128, 128, 128, 0.25);
    border-bottom: 1px solid rgba(128, 128, 128, 0.35);
    padding: 3px 6px;
}
QTabBar::tab {
    background-color: palette(window);
    color: palette(window-text);
    border: 1px solid rgba(128, 128, 128, 0.3);
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 3px 8px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: palette(button);
    color: palette(button-text);
    border-color: palette(highlight);
    border-bottom: 2px solid palette(highlight);
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: palette(alternate-base);
}
QLineEdit, QComboBox {
    background-color: palette(base);
    color: palette(text);
    border: 1px solid rgba(128, 128, 128, 0.4);
    border-radius: 3px;
    padding: 2px 6px;
    selection-background-color: palette(highlight);
    selection-color: palette(highlighted-text);
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid palette(highlight);
}
QPushButton {
    background-color: palette(button);
    color: palette(button-text);
    border: 1px solid rgba(128, 128, 128, 0.35);
    border-radius: 3px;
    padding: 3px 8px;
}
QPushButton:hover {
    border-color: palette(highlight);
}
QPushButton:checked, QPushButton:pressed {
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
"""


def setup_qt_environment():
    """Configura caminhos de bibliotecas e plugins Qt antes da inicialização do QApplication."""
    plugin_paths = [
        "/usr/lib/qt6/plugins",
        "/usr/lib64/qt6/plugins",
        "/usr/local/lib/qt6/plugins",
    ]
    for p in plugin_paths:
        if os.path.isdir(p):
            QCoreApplication.addLibraryPath(p)

    # Limpa QT_STYLE_OVERRIDE para evitar aviso 'invalid style override kvantum' na inicialização;
    # o estilo real (ex: Breeze / Fusion) é aplicado logo em seguida por apply_system_theme().
    os.environ.pop("QT_STYLE_OVERRIDE", None)



def _parse_rgb(value: str) -> Optional[RGB]:
    match = HEX_COLOR_RE.fullmatch(str(value).strip())
    if not match:
        return None
    raw = match.group(1)
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def _rgb_to_qcolor(rgb: RGB) -> QColor:
    return QColor(
        max(0, min(255, int(rgb[0]))),
        max(0, min(255, int(rgb[1]))),
        max(0, min(255, int(rgb[2]))),
    )


def _mix_rgb(first: RGB, second: RGB, amount: float) -> RGB:
    amount = max(0.0, min(1.0, amount))
    return (
        round(first[0] * (1.0 - amount) + second[0] * amount),
        round(first[1] * (1.0 - amount) + second[1] * amount),
        round(first[2] * (1.0 - amount) + second[2] * amount),
    )


def _relative_luminance(color: RGB) -> float:
    def _chan(val: int) -> float:
        norm = val / 255.0
        return norm / 12.92 if norm <= 0.04045 else ((norm + 0.055) / 1.055) ** 2.4

    r, g, b = _chan(color[0]), _chan(color[1]), _chan(color[2])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(first: RGB, second: RGB) -> float:
    l1, l2 = _relative_luminance(first), _relative_luminance(second)
    bright, dark = (l1, l2) if l1 >= l2 else (l2, l1)
    return (bright + 0.05) / (dark + 0.05)


def _ensure_contrast(color: RGB, foreground: RGB, background: RGB, minimum: float) -> RGB:
    adjusted = color
    for _ in range(12):
        if _contrast_ratio(adjusted, foreground) >= minimum:
            break
        adjusted = _mix_rgb(adjusted, background, 0.12)
    return adjusted


def get_wal_paths() -> Tuple[str, str]:
    """Retorna os caminhos para colors.json do Pywal e last-rgb do OpenRGB/cw.sh."""
    cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    wal_json = os.path.join(cache_home, "wal", "colors.json")
    rgb_state = os.path.join(cache_home, "cw", "last-rgb")
    return wal_json, rgb_state


def is_wallpaper_theme_enabled_in_settings() -> bool:
    """Lê ~/.config/qdir/settings.json para saber se o tema do wallpaper está ativo (padrão: True)."""
    cfg_path = os.path.expanduser("~/.config/qdir/settings.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if "use_wallpaper_theme" in data:
                return bool(data["use_wallpaper_theme"])
        except Exception:
            pass
    return True


def _build_pywal_palette(app: QApplication) -> Optional[QPalette]:
    """
    Constrói uma QPalette a partir de ~/.cache/wal/colors.json e ~/.cache/cw/last-rgb,
    seguindo a mesma derivação de cores e contraste do QuickShell (update-wallpaper-theme.py).
    """
    wal_json_path, rgb_state_path = get_wal_paths()
    if not os.path.isfile(wal_json_path):
        return None

    try:
        with open(wal_json_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception as e:
        print(f"[QDir Theme] Erro ao ler {wal_json_path}: {e}", file=sys.stderr)
        return None

    special = doc.get("special", {})
    wal_colors = doc.get("colors", {})

    bg_rgb = _parse_rgb(special.get("background", ""))
    fg_rgb = _parse_rgb(special.get("foreground", ""))
    if not bg_rgb or not fg_rgb:
        return None

    # Garante fundo escuro confortável (mesma regra do update-wallpaper-theme.py)
    if _relative_luminance(bg_rgb) > 0.18:
        bg_rgb = _mix_rgb(bg_rgb, (0, 0, 0), 0.58)

    # Garante contraste de leitura do texto principal
    white: RGB = (245, 245, 245)
    black: RGB = (18, 18, 18)
    if _contrast_ratio(bg_rgb, fg_rgb) < 4.5:
        fg_rgb = white if _contrast_ratio(bg_rgb, white) >= _contrast_ratio(bg_rgb, black) else black

    # Cor de destaque: prioriza ~/.cache/cw/last-rgb (OpenRGB) e cai para color1 do Pywal
    accent_source: Optional[RGB] = None
    if os.path.isfile(rgb_state_path):
        try:
            with open(rgb_state_path, "r", encoding="utf-8") as f:
                saved_rgb = f.read().strip()
            accent_source = _parse_rgb(saved_rgb)
        except Exception:
            pass

    if not accent_source:
        accent_source = _parse_rgb(wal_colors.get("color1", "#00AFBF")) or (0, 175, 191)

    primary_rgb = _ensure_contrast(accent_source, fg_rgb, bg_rgb, 3.1)
    accent_rgb = _ensure_contrast(_mix_rgb(accent_source, fg_rgb, 0.24), fg_rgb, bg_rgb, 2.7)

    # Texto sobre o Highlight (escolhe branco ou escuro conforme a luminância do primary)
    hl_text_rgb = white if _contrast_ratio(primary_rgb, white) >= _contrast_ratio(primary_rgb, black) else black

    # Superfícies derivadas da paleta do wallpaper
    base_rgb = bg_rgb
    alt_base_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.05)
    window_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.08)
    button_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.13)
    light_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.24)
    midlight_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.18)
    mid_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.28)
    dark_rgb = _mix_rgb(bg_rgb, (0, 0, 0), 0.35)
    shadow_rgb: RGB = (8, 8, 8)
    tooltip_bg_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.12)
    placeholder_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.46)
    disabled_fg_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.38)
    disabled_btn_rgb = _mix_rgb(bg_rgb, fg_rgb, 0.07)

    pal = QPalette(app.palette())

    role_map = {
        QPalette.ColorRole.Window: _rgb_to_qcolor(window_rgb),
        QPalette.ColorRole.WindowText: _rgb_to_qcolor(fg_rgb),
        QPalette.ColorRole.Base: _rgb_to_qcolor(base_rgb),
        QPalette.ColorRole.AlternateBase: _rgb_to_qcolor(alt_base_rgb),
        QPalette.ColorRole.ToolTipBase: _rgb_to_qcolor(tooltip_bg_rgb),
        QPalette.ColorRole.ToolTipText: _rgb_to_qcolor(fg_rgb),
        QPalette.ColorRole.PlaceholderText: _rgb_to_qcolor(placeholder_rgb),
        QPalette.ColorRole.Text: _rgb_to_qcolor(fg_rgb),
        QPalette.ColorRole.Button: _rgb_to_qcolor(button_rgb),
        QPalette.ColorRole.ButtonText: _rgb_to_qcolor(fg_rgb),
        QPalette.ColorRole.BrightText: _rgb_to_qcolor(white),
        QPalette.ColorRole.Light: _rgb_to_qcolor(light_rgb),
        QPalette.ColorRole.Midlight: _rgb_to_qcolor(midlight_rgb),
        QPalette.ColorRole.Mid: _rgb_to_qcolor(mid_rgb),
        QPalette.ColorRole.Dark: _rgb_to_qcolor(dark_rgb),
        QPalette.ColorRole.Shadow: _rgb_to_qcolor(shadow_rgb),
        QPalette.ColorRole.Highlight: _rgb_to_qcolor(primary_rgb),
        QPalette.ColorRole.HighlightedText: _rgb_to_qcolor(hl_text_rgb),
        QPalette.ColorRole.Link: _rgb_to_qcolor(accent_rgb),
        QPalette.ColorRole.LinkVisited: _rgb_to_qcolor(primary_rgb),
    }

    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        for role, qcol in role_map.items():
            pal.setColor(group, role, qcol)

    # Grupo Disabled
    for role, qcol in role_map.items():
        pal.setColor(QPalette.ColorGroup.Disabled, role, qcol)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, _rgb_to_qcolor(disabled_fg_rgb))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, _rgb_to_qcolor(disabled_fg_rgb))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, _rgb_to_qcolor(disabled_fg_rgb))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Button, _rgb_to_qcolor(disabled_btn_rgb))
    pal.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Highlight,
        _rgb_to_qcolor(_mix_rgb(bg_rgb, primary_rgb, 0.45)),
    )

    return pal


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


def _detect_system_icon_theme() -> Optional[str]:
    """Detecta o tema de ícones configurado no GTK, gsettings ou temas instalados."""
    for gtk_path in ["~/.config/gtk-3.0/settings.ini", "~/.config/gtk-4.0/settings.ini"]:
        fpath = os.path.expanduser(gtk_path)
        if os.path.isfile(fpath):
            try:
                cp = configparser.ConfigParser()
                cp.read(fpath)
                theme = cp.get("Settings", "gtk-icon-theme-name", fallback="").strip().strip("\"'")
                if theme:
                    return theme
            except Exception:
                pass

    try:
        import subprocess
        res = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        theme = res.stdout.strip().strip("'\"")
        if theme and theme != "hicolor":
            return theme
    except Exception:
        pass

    candidate_dirs = [
        os.path.expanduser("~/.local/share/icons"),
        os.path.expanduser("~/.icons"),
        "/usr/share/icons",
    ]
    preferred = [
        "Tela-dracula-dark",
        "Tela-dark",
        "Papirus-Dark",
        "breeze-dark",
        "breeze",
        "Adwaita",
        "Pop",
    ]
    for pref in preferred:
        for cdir in candidate_dirs:
            if os.path.isdir(os.path.join(cdir, pref)):
                return pref

    return None


def apply_system_theme(app: QApplication, use_wallpaper: Optional[bool] = None) -> bool:
    """
    Detecta e aplica o tema do sistema:
    - Se use_wallpaper=True (ou ativo no settings.json), aplica a paleta dinâmica do Wallpaper (Pywal + OpenRGB).
    - Caso contrário (ou como fallback), aplica o tema configurado no Qt6 Settings (qt6ct).
    """
    if use_wallpaper is None:
        use_wallpaper = is_wallpaper_theme_enabled_in_settings()

    conf_path = os.path.expanduser("~/.config/qt6ct/qt6ct.conf")
    applied = False
    used_pywal = False

    # 1. Configura estilo base, fontes e ícones do qt6ct
    qt6ct_palette: Optional[QPalette] = None
    if os.path.isfile(conf_path):
        cp = configparser.ConfigParser()
        try:
            cp.read(conf_path)

            style_name = cp.get("Appearance", "style", fallback="").strip()
            if style_name:
                available = QStyleFactory.keys()
                matched = next((s for s in available if s.lower() == style_name.lower()), None)
                if matched:
                    app.setStyle(matched)
                elif "Fusion" in available:
                    app.setStyle("Fusion")

            custom_palette = cp.getboolean("Appearance", "custom_palette", fallback=True)
            color_scheme = cp.get("Appearance", "color_scheme_path", fallback="").strip()
            if custom_palette and color_scheme:
                color_scheme = os.path.expanduser(os.path.expandvars(color_scheme))
                qt6ct_palette = _parse_qt6ct_palette(color_scheme, app)

            font_str = cp.get("Fonts", "general", fallback="").strip().strip("\"'")
            if font_str:
                font = QFont()
                if font.fromString(font_str):
                    app.setFont(font)

            icon_theme = cp.get("Appearance", "icon_theme", fallback="").strip().strip("\"'")
            if not icon_theme:
                icon_theme = _detect_system_icon_theme()
            if icon_theme:
                QIcon.setThemeName(icon_theme)

        except Exception as e:
            print(f"[QDir Theme] Erro ao processar qt6ct.conf: {e}", file=sys.stderr)
    else:
        icon_theme = _detect_system_icon_theme()
        if icon_theme:
            QIcon.setThemeName(icon_theme)

    # 2. Se modo Wallpaper estiver ativo, tenta aplicar a paleta Pywal + OpenRGB
    if use_wallpaper:
        pywal_pal = _build_pywal_palette(app)
        if pywal_pal is not None:
            app.setPalette(pywal_pal)
            applied = True
            used_pywal = True

    # 3. Se não usou Pywal, aplica a paleta do qt6ct
    if not applied and qt6ct_palette is not None:
        app.setPalette(qt6ct_palette)
        applied = True

    # 4. Fallback escuro caso nem Pywal nem qt6ct estejam presentes
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

    # 5. Aplica QSS sem duplicar em recarregamentos
    if used_pywal:
        app.setStyleSheet(BASE_MENU_QSS + "\n" + WALLPAPER_EXTRA_QSS)
    else:
        app.setStyleSheet(BASE_MENU_QSS)

    return applied


class WallpaperThemeWatcher(QObject):
    """
    Monitora alterações em ~/.cache/wal/colors.json e ~/.cache/cw/last-rgb
    (incluindo substituições atômicas via mv nos diretórios pai) e dispara hot-reload no QDir.
    """

    def __init__(self, app: QApplication, on_theme_updated: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.app = app
        self.on_theme_updated = on_theme_updated
        self.enabled: bool = is_wallpaper_theme_enabled_in_settings()

        self.watcher = QFileSystemWatcher(self)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(180)
        self._debounce.timeout.connect(self._apply_reload)

        self.watcher.fileChanged.connect(self._on_fs_event)
        self.watcher.directoryChanged.connect(self._on_fs_event)
        self._register_paths()

    def _register_paths(self):
        wal_json, rgb_state = get_wal_paths()
        for path in (wal_json, rgb_state, os.path.dirname(wal_json), os.path.dirname(rgb_state)):
            if os.path.exists(path) and path not in self.watcher.files() and path not in self.watcher.directories():
                self.watcher.addPath(path)

    def _on_fs_event(self, _path: str):
        # Re-registra arquivos caso tenham sido recriados atomicamente (mv tmp -> destino)
        self._register_paths()
        if self.enabled:
            self._debounce.start()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self._register_paths()
        self._apply_reload()

    def _apply_reload(self):
        apply_system_theme(self.app, use_wallpaper=self.enabled)
        if self.on_theme_updated:
            self.on_theme_updated()

