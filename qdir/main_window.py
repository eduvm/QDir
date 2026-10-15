"""
MainWindow do QDir Linux.
Janela principal integrando os 4 painéis, LayoutManager, barra de ferramentas
com os 12 layouts, barra de menus completa, favoritos, exportação e persistência de sessões.
"""

import os
import shutil
from typing import List, Optional

from PyQt6.QtCore import QDir, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from qdir.clipboard_manager import QDirClipboard
from qdir.color_engine import ColorEngine
from qdir.export_engine import export_to_csv, export_to_html, export_to_txt
from qdir.file_ops import BatchRenameDialog, open_in_terminal
from qdir.layout_manager import LayoutManager
from qdir.pane import QDirPane
from qdir.session_manager import SessionManager
from qdir.theme_manager import WallpaperThemeWatcher, is_wallpaper_theme_enabled_in_settings


from qdir.color_dialog import ColorRulesDialog
from qdir.ui_icons import get_ui_icon


class QDirMainWindow(QMainWindow):
    """Janela principal do QDir Linux."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QDir Linux - Quad File Explorer")
        self.resize(1200, 800)
        self.use_wallpaper_theme: bool = is_wallpaper_theme_enabled_in_settings()

        # 1. Carrega motor de cores (tenta Q-Dir.ini na pasta do projeto se existir)
        ini_path = os.path.join(os.path.dirname(__file__), "..", "Q-Dir Windows", "Q-Dir.ini")
        if not os.path.exists(ini_path):
            ini_path = os.path.join(os.getcwd(), "Q-Dir Windows", "Q-Dir.ini")
        self.color_engine = ColorEngine(ini_path if os.path.exists(ini_path) else None)

        # 2. Cria os 4 painéis independentes
        self.panes: List[QDirPane] = []
        for i in range(1, 5):
            pane = QDirPane(pane_id=i, color_engine=self.color_engine, parent=self)
            pane.activated.connect(self.on_pane_activated)
            pane.status_updated.connect(self.on_pane_status_updated)
            pane.maximize_requested.connect(self.on_pane_maximize_requested)
            self.panes.append(pane)

        self.active_pane = self.panes[0]
        self.active_pane.set_active(True)

        # 3. Cria o LayoutManager com os 12 layouts
        self.layout_manager = LayoutManager(self.panes, parent=self)
        self.setCentralWidget(self.layout_manager)

        # 4. Sincroniza árvore compartilhada quando o caminho mudar
        for pane in self.panes:
            pane.path_changed.connect(self.layout_manager.sync_shared_tree)

        # 5. Constrói Menus e Toolbars
        self._build_menu_bar()
        self._build_tool_bar()
        self._build_status_bar()

        # 6. Carrega configurações salvas (larguras de colunas, layout, pastas, abas)
        self.load_settings()

        # 7. Sincroniza estado da área de transferência
        QDirClipboard.clipboard_changed.connect(self.on_clipboard_changed)

        # 8. Monitora troca de Wallpaper (Pywal + OpenRGB) em tempo real
        self.theme_watcher = WallpaperThemeWatcher(
            QApplication.instance(),
            on_theme_updated=self.on_theme_updated,
            parent=self,
        )
        self.theme_watcher.enabled = self.use_wallpaper_theme


    def refresh_all_panes(self):
        """Atualiza a listagem de arquivos de todos os painéis."""
        for p in self.panes:
            p.refresh()

    def on_clipboard_changed(self):
        """Atualiza a visualização dos painéis quando o clipboard de recorte/cópia muda."""
        for p in self.panes:
            p.table_view.viewport().update()

    def on_pane_activated(self, pane: QDirPane):
        if self.active_pane != pane:
            self.active_pane.set_active(False)
            self.active_pane = pane
            self.active_pane.set_active(True)
            self.layout_manager.sync_shared_tree(pane.current_path)
            self.update_status_bar()

    def on_pane_status_updated(self, status: str):
        if self.sender() == self.active_pane:
            self.lbl_pane_status.setText(status)

    def _build_menu_bar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
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
        """)

        # --- Menu Arquivo ---
        menu_file = menubar.addMenu("&Arquivo")

        act_new_tab = menu_file.addAction("Nova Aba")
        act_new_tab.setShortcut(QKeySequence("Ctrl+T"))
        act_new_tab.triggered.connect(lambda: self.active_pane.add_tab())

        act_close_tab = menu_file.addAction("Fechar Aba")
        act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        act_close_tab.triggered.connect(lambda: self.active_pane.on_tab_close(self.active_pane.tabs.currentIndex()))

        menu_file.addSeparator()

        act_term = menu_file.addAction("Abrir no Terminal")
        act_term.setShortcut(QKeySequence("Ctrl+Alt+T"))
        act_term.triggered.connect(lambda: open_in_terminal(self.active_pane.current_path))

        menu_file.addSeparator()

        # Submenu Exportar
        menu_export = menu_file.addMenu("Exportar Lista de Arquivos")
        act_exp_html = menu_export.addAction("Exportar para HTML...")
        act_exp_html.triggered.connect(lambda: self.export_active_dir("html"))
        act_exp_csv = menu_export.addAction("Exportar para CSV...")
        act_exp_csv.triggered.connect(lambda: self.export_active_dir("csv"))
        act_exp_txt = menu_export.addAction("Exportar para TXT...")
        act_exp_txt.triggered.connect(lambda: self.export_active_dir("txt"))

        menu_file.addSeparator()

        act_save_sess = menu_file.addAction("Salvar Sessão (.qdr / .json)...")
        act_save_sess.triggered.connect(self.save_current_session)

        act_load_sess = menu_file.addAction("Carregar Sessão...")
        act_load_sess.triggered.connect(self.load_session_dialog)

        menu_file.addSeparator()

        act_quit = menu_file.addAction("Sair")
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        # --- Menu Editar ---
        menu_edit = menubar.addMenu("&Editar")

        act_cut = menu_edit.addAction("Recortar")
        act_cut.setShortcut(QKeySequence("Ctrl+X"))
        act_cut.triggered.connect(lambda: self.active_pane.cut_selection())

        act_copy = menu_edit.addAction("Copiar")
        act_copy.setShortcut(QKeySequence("Ctrl+C"))
        act_copy.triggered.connect(lambda: self.active_pane.copy_selection())

        act_paste = menu_edit.addAction("Colar")
        act_paste.setShortcut(QKeySequence("Ctrl+V"))
        act_paste.triggered.connect(lambda: self.active_pane.paste_clipboard())

        menu_edit.addSeparator()

        act_sel_all = menu_edit.addAction("Selecionar Tudo")
        act_sel_all.setShortcut(QKeySequence("Ctrl+A"))
        act_sel_all.triggered.connect(lambda: self.active_pane.table_view.selectAll())

        act_rename = menu_edit.addAction("Renomear")
        act_rename.setShortcut(QKeySequence("F2"))
        act_rename.triggered.connect(lambda: self.active_pane.rename_single())

        act_batch_rename = menu_edit.addAction("Renomeação em Lote...")
        act_batch_rename.triggered.connect(self.open_batch_rename)

        menu_edit.addSeparator()

        act_trash = menu_edit.addAction("Mover para Lixeira")
        act_trash.setShortcut(QKeySequence("Delete"))
        act_trash.triggered.connect(lambda: self.active_pane.delete_to_trash())

        act_del_perm = menu_edit.addAction("Excluir Permanentemente")
        act_del_perm.setShortcut(QKeySequence("Shift+Delete"))
        act_del_perm.triggered.connect(lambda: self.active_pane.delete_permanently())

        # --- Menu Layouts ---
        menu_layouts = menubar.addMenu("&Layouts")
        layout_group = QActionGroup(self)
        self.layout_actions = []

        for idx, name in enumerate(LayoutManager.LAYOUT_NAMES):
            act = menu_layouts.addAction(f"&{idx+1} - {name}")
            act.setCheckable(True)
            if idx == 0:
                act.setChecked(True)
            act.triggered.connect(lambda checked, i=idx: self.switch_layout(i))
            layout_group.addAction(act)
            self.layout_actions.append(act)

        # --- Menu Exibir ---
        menu_view = menubar.addMenu("&Exibir")

        menu_tree = menu_view.addMenu("Modo de Árvore de Pastas")
        tree_group = QActionGroup(self)
        tree_options = [("Sem Árvore", 0), ("4 Árvores (Individuais)", 1), ("1 Árvore Compartilhada", 2)]
        for label, val in tree_options:
            act = menu_tree.addAction(label)
            act.setCheckable(True)
            if val == 0:
                act.setChecked(True)
            act.triggered.connect(lambda checked, v=val: self.layout_manager.set_tree_mode(v))
            tree_group.addAction(act)

        menu_view.addSeparator()

        act_hidden = menu_view.addAction("Exibir Arquivos Ocultos")
        act_hidden.setCheckable(True)
        act_hidden.setShortcut(QKeySequence("Ctrl+H"))
        act_hidden.triggered.connect(self.toggle_all_hidden)

        act_refresh_all = menu_view.addAction("Atualizar Todos os Painéis")
        act_refresh_all.setShortcut(QKeySequence("F5"))
        act_refresh_all.triggered.connect(self.refresh_all_panes)

        menu_view.addSeparator()

        self.act_maximize = menu_view.addAction("Maximizar / Restaurar Painel Ativo")
        self.act_maximize.setCheckable(True)
        self.act_maximize.setShortcuts([QKeySequence("Ctrl+M"), QKeySequence("F11")])
        self.act_maximize.triggered.connect(self.toggle_maximize_active_pane)

        menu_view.addSeparator()

        self.act_wallpaper_theme = menu_view.addAction("🎨 Tema Dinâmico do Wallpaper (Pywal / OpenRGB)")
        self.act_wallpaper_theme.setCheckable(True)
        self.act_wallpaper_theme.setChecked(self.use_wallpaper_theme)
        self.act_wallpaper_theme.triggered.connect(self.toggle_wallpaper_theme)

        # --- Menu Favoritos ---
        menu_fav = menubar.addMenu("&Favoritos")
        act_add_fav = menu_fav.addAction("Adicionar Pasta Atual aos Favoritos")
        act_add_fav.triggered.connect(self.add_current_to_fav)

        menu_fav.addSeparator()
        self.quick_favs = [
            ("Pasta Pessoal (Home)", os.path.expanduser("~")),
            ("Documentos", os.path.expanduser("~/Documentos")),
            ("Downloads", os.path.expanduser("~/Downloads")),
            ("Desktop", os.path.expanduser("~/Desktop")),
            ("Raiz do Sistema (/)", "/"),
        ]
        for title, path in self.quick_favs:
            if os.path.exists(path):
                act = menu_fav.addAction(title)
                act.triggered.connect(lambda checked, p=path: self.active_pane.navigate_to(p))

        # --- Menu Ferramentas ---
        menu_tools = menubar.addMenu("Ferramen&tas")
        act_rules = menu_tools.addAction("Regras de Cores (Filter2)...")
        act_rules.triggered.connect(self.show_color_rules)

        menu_tools.addSeparator()
        self.act_wallpaper_theme_tools = menu_tools.addAction("🎨 Tema Dinâmico do Wallpaper (Pywal / OpenRGB)")
        self.act_wallpaper_theme_tools.setCheckable(True)
        self.act_wallpaper_theme_tools.setChecked(self.use_wallpaper_theme)
        self.act_wallpaper_theme_tools.triggered.connect(self.toggle_wallpaper_theme)

        # --- Menu Ajuda ---
        menu_help = menubar.addMenu("A&juda")
        act_about = menu_help.addAction("Sobre o QDir Linux")
        act_about.triggered.connect(self.show_about)

    def _build_tool_bar(self):
        toolbar = QToolBar("Barra Principal")
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Seletor Rápido dos 12 Layouts
        toolbar.addWidget(QLabel(" Layout: "))
        self.combo_layout = QComboBox()
        for idx, name in enumerate(LayoutManager.LAYOUT_NAMES):
            self.combo_layout.addItem(f"{idx+1}. {name}")
        self.combo_layout.currentIndexChanged.connect(self.switch_layout)
        toolbar.addWidget(self.combo_layout)

        # Botão Maximizar Painel Ativo
        self.btn_maximize = QPushButton(" ⛶ Maximizar")
        self.btn_maximize.setToolTip("Maximizar / Restaurar Painel Ativo (Ctrl+M ou F11)")
        self.btn_maximize.setCheckable(True)
        self.btn_maximize.clicked.connect(self.toggle_maximize_active_pane)
        toolbar.addWidget(self.btn_maximize)

        toolbar.addSeparator()

        # Seletor de Árvore
        toolbar.addWidget(QLabel(" Árvores: "))
        self.combo_tree = QComboBox()
        self.combo_tree.addItems(["Sem Árvore", "4 Árvores", "1 Compartilhada"])
        self.combo_tree.currentIndexChanged.connect(self.layout_manager.set_tree_mode)
        toolbar.addWidget(self.combo_tree)

        toolbar.addSeparator()

        # Botão Terminal
        self.btn_term = QPushButton(" Terminal")
        self.btn_term.setIcon(get_ui_icon("terminal"))
        self.btn_term.setIconSize(QSize(16, 16))
        self.btn_term.clicked.connect(lambda: open_in_terminal(self.active_pane.current_path))
        toolbar.addWidget(self.btn_term)

        # Botão Atualizar Todos
        self.btn_refresh = QPushButton(" Atualizar")
        self.btn_refresh.setIcon(get_ui_icon("refresh"))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.clicked.connect(self.refresh_all_panes)
        toolbar.addWidget(self.btn_refresh)

        # Botão Exportar
        self.btn_export = QPushButton(" Exportar...")
        self.btn_export.setIcon(get_ui_icon("export"))
        self.btn_export.setIconSize(QSize(16, 16))
        self.btn_export.clicked.connect(lambda: self.export_active_dir("html"))
        toolbar.addWidget(self.btn_export)

        toolbar.addSeparator()

        # Botão Salvar Sessão
        self.btn_session = QPushButton(" Salvar Sessão")
        self.btn_session.setIcon(get_ui_icon("session"))
        self.btn_session.setIconSize(QSize(16, 16))
        self.btn_session.clicked.connect(self.save_current_session)
        toolbar.addWidget(self.btn_session)

    def _build_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)

        self.lbl_pane_status = QLabel("Pronto")
        status.addWidget(self.lbl_pane_status, stretch=1)

        self.lbl_disk_free = QLabel("")
        self.lbl_disk_free.setStyleSheet("padding-right: 10px;")
        status.addPermanentWidget(self.lbl_disk_free)

        self.update_status_bar()

    def update_status_bar(self):
        self.active_pane.update_status()
        # Calcula espaço livre no ponto de montagem do caminho ativo
        try:
            usage = shutil.disk_usage(self.active_pane.current_path)
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            self.lbl_disk_free.setText(f"Disco: {free_gb:.1f} GB livres de {total_gb:.1f} GB")
        except Exception:
            self.lbl_disk_free.setText("")

    def switch_layout(self, layout_id: int):
        self.combo_layout.setCurrentIndex(layout_id)
        if 0 <= layout_id < len(self.layout_actions):
            self.layout_actions[layout_id].setChecked(True)
        if hasattr(self, "btn_maximize"):
            self.btn_maximize.setChecked(False)
            self.btn_maximize.setText(" ⛶ Maximizar")
        if hasattr(self, "act_maximize"):
            self.act_maximize.setChecked(False)
        self.layout_manager.apply_layout(layout_id)

    def on_pane_maximize_requested(self, pane_idx: int):
        is_max = self.layout_manager.toggle_maximize_pane(pane_idx)
        if hasattr(self, "btn_maximize"):
            self.btn_maximize.setChecked(is_max)
            self.btn_maximize.setText(" ⮌ Restaurar" if is_max else " ⛶ Maximizar")
        if hasattr(self, "act_maximize"):
            self.act_maximize.setChecked(is_max)

    def toggle_maximize_active_pane(self):
        active_idx = self.panes.index(self.active_pane) if self.active_pane in self.panes else 0
        self.on_pane_maximize_requested(active_idx)

    def toggle_wallpaper_theme(self, checked: bool):
        """Ativa ou desativa a sincronização de cores com o Wallpaper (Pywal + OpenRGB) em tempo real."""
        self.use_wallpaper_theme = bool(checked)
        if hasattr(self, "act_wallpaper_theme"):
            self.act_wallpaper_theme.blockSignals(True)
            self.act_wallpaper_theme.setChecked(self.use_wallpaper_theme)
            self.act_wallpaper_theme.blockSignals(False)
        if hasattr(self, "act_wallpaper_theme_tools"):
            self.act_wallpaper_theme_tools.blockSignals(True)
            self.act_wallpaper_theme_tools.setChecked(self.use_wallpaper_theme)
            self.act_wallpaper_theme_tools.blockSignals(False)
        self.save_settings()
        if hasattr(self, "theme_watcher"):
            self.theme_watcher.set_enabled(self.use_wallpaper_theme)

    def on_theme_updated(self):
        """Callback disparado quando a paleta do Wallpaper (ou alternância para qt6ct) é aplicada."""
        for p in self.panes:
            p.refresh_theme()
        if hasattr(self, "btn_term"):
            self.btn_term.setIcon(get_ui_icon("terminal"))
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setIcon(get_ui_icon("refresh"))
        if hasattr(self, "btn_export"):
            self.btn_export.setIcon(get_ui_icon("export"))
        if hasattr(self, "btn_session"):
            self.btn_session.setIcon(get_ui_icon("session"))
        if hasattr(self, "layout_manager") and hasattr(self.layout_manager, "shared_tree"):
            self.layout_manager.shared_tree.viewport().update()
        self.update()

    def toggle_all_hidden(self, checked: bool):
        for pane in self.panes:
            pane.chk_hidden.setChecked(checked)

    def refresh_all_panes(self):
        for pane in self.panes:
            pane.refresh()
        self.update_status_bar()


    def open_batch_rename(self):
        selected = self.active_pane.get_selected_paths()
        if len(selected) > 1:
            BatchRenameDialog(selected, self).exec()
            self.active_pane.refresh()
        else:
            QMessageBox.information(
                self,
                "Renomeação em Lote",
                "Selecione dois ou mais arquivos no painel ativo para usar a renomeação em lote.",
            )

    def export_active_dir(self, fmt: str):
        cur_dir = self.active_pane.current_path
        ext = fmt.lower()
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar Listagem de Arquivos ({ext.upper()})",
            os.path.join(cur_dir, f"lista_arquivos.{ext}"),
            f"Arquivos {ext.upper()} (*.{ext})",
        )
        if filepath:
            try:
                if ext == "html":
                    export_to_html(cur_dir, filepath)
                elif ext == "csv":
                    export_to_csv(cur_dir, filepath)
                elif ext == "txt":
                    export_to_txt(cur_dir, filepath)
                QMessageBox.information(self, "Exportado", f"Listagem exportada com sucesso para:\n{filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Erro na Exportação", f"Falha ao exportar: {e}")

    def add_current_to_fav(self):
        path = self.active_pane.current_path
        fav_dir = os.path.expanduser("~/.config/qdir/favorites")
        os.makedirs(fav_dir, exist_ok=True)
        link_name = os.path.basename(path) or "Raiz"
        link_path = os.path.join(fav_dir, link_name)
        try:
            if not os.path.exists(link_path):
                os.symlink(path, link_path)
            QMessageBox.information(self, "Favoritos", f"Pasta adicionada aos favoritos:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Não foi possível criar favorito: {e}")

    def save_current_session(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Sessão do QDir",
            os.path.expanduser("~/sessao.qdr"),
            "Sessões QDir (*.qdr);;Sessões JSON (*.json)",
        )
        if filepath:
            session_data = {
                "layout_id": self.layout_manager.current_layout_id,
                "tree_mode": self.layout_manager.current_tree_mode,
                "splitters": [5000, 5000, 5000],
                "folders": [p.current_path for p in self.panes],
            }
            try:
                if filepath.endswith(".json"):
                    SessionManager.save_json(filepath, session_data)
                else:
                    SessionManager.save_qdr(filepath, session_data)
                QMessageBox.information(self, "Sessão Salva", f"Sessão salva com sucesso em:\n{filepath}")
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Falha ao salvar sessão: {e}")

    def load_session_dialog(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Carregar Sessão do QDir",
            os.path.expanduser("~"),
            "Sessões (*.qdr *.json);;Todas (*)",
        )
        if filepath:
            if filepath.endswith(".json"):
                data = SessionManager.load_json(filepath)
            else:
                data = SessionManager.parse_qdr(filepath)
            self._apply_loaded_session(data)

    def load_session_qdr(self, filepath: str):
        try:
            data = SessionManager.parse_qdr(filepath)
            self._apply_loaded_session(data)
        except Exception:
            pass

    def _apply_loaded_session(self, data: dict):
        layout_id = data.get("layout_id", 0)
        self.switch_layout(layout_id)

        tree_mode = data.get("tree_mode", 0)
        self.combo_tree.setCurrentIndex(tree_mode)

        folders = data.get("folders", [])
        for i, path in enumerate(folders):
            if i < len(self.panes) and os.path.isdir(path):
                self.panes[i].navigate_to(path)

    def get_settings_path(self) -> str:
        cfg_dir = os.path.expanduser("~/.config/qdir")
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, "settings.json")

    def save_settings(self):
        """Salva larguras de colunas, layout, largura da árvore de diretórios, abas e caminhos ao fechar."""
        try:
            cfg_path = self.get_settings_path()
            panes_data = []
            for p in self.panes:
                tabs_list = []
                for i in range(p.tabs.count()):
                    tab_path = p.get_tab_path(i)
                    is_locked = p.is_tab_locked(i)
                    tab_data = p.get_tab_data(i)
                    tabs_list.append({
                        "path": tab_path,
                        "locked": is_locked,
                        "root_path": tab_data.get("root_path", tab_path),
                        "original_title": tab_data.get("original_title", os.path.basename(tab_path) or "/"),
                    })
                panes_data.append({
                    "current_path": p.current_path,
                    "column_widths": p.get_column_widths(),
                    "tree_width": p.get_tree_width(),
                    "tabs": tabs_list if tabs_list else [{"path": p.current_path, "locked": False}],
                })

            data = {
                "layout_id": self.layout_manager.current_layout_id,
                "tree_mode": self.layout_manager.current_tree_mode,
                "shared_tree_width": self.layout_manager.get_shared_tree_width(),
                "window_width": self.width(),
                "window_height": self.height(),
                "is_maximized": self.isMaximized(),
                "use_wallpaper_theme": self.use_wallpaper_theme,
                "panes": panes_data,
            }
            import json
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar configurações do QDir: {e}")

    def load_settings(self):
        """Carrega larguras de colunas, largura da árvore, layout e abas salvas."""
        cfg_path = self.get_settings_path()
        if os.path.exists(cfg_path):
            try:
                import json
                with open(cfg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if "use_wallpaper_theme" in data:
                    self.use_wallpaper_theme = bool(data["use_wallpaper_theme"])
                    if hasattr(self, "act_wallpaper_theme"):
                        self.act_wallpaper_theme.setChecked(self.use_wallpaper_theme)
                    if hasattr(self, "act_wallpaper_theme_tools"):
                        self.act_wallpaper_theme_tools.setChecked(self.use_wallpaper_theme)

                if data.get("is_maximized"):
                    self.showMaximized()
                elif "window_width" in data and "window_height" in data:
                    self.resize(data["window_width"], data["window_height"])

                if "shared_tree_width" in data:
                    self.layout_manager.set_shared_tree_width(int(data["shared_tree_width"]))


                layout_id = data.get("layout_id", 0)
                self.switch_layout(layout_id)

                panes_data = data.get("panes", [])
                for i, p_info in enumerate(panes_data):
                    if i < len(self.panes):
                        pane = self.panes[i]
                        # Restaura largura da árvore individual antes de ativar o tree_mode
                        tree_w = p_info.get("tree_width")
                        if tree_w:
                            pane.set_tree_width(int(tree_w))

                        tabs = p_info.get("tabs", [])
                        if tabs:
                            while pane.tabs.count() > 1:
                                pane.tabs.removeTab(pane.tabs.count() - 1)

                            first_t = tabs[0]
                            first_path = first_t.get("path") if isinstance(first_t, dict) else first_t
                            first_locked = first_t.get("locked", False) if isinstance(first_t, dict) else False
                            first_root = first_t.get("root_path") if isinstance(first_t, dict) else None
                            first_title = first_t.get("original_title") if isinstance(first_t, dict) else None

                            if first_path and os.path.isdir(first_path):
                                pane.set_tab_locked(0, False)
                                pane.navigate_to(first_path, record_history=False)
                                if first_locked:
                                    pane.set_tab_locked(0, True, root_path=first_root, original_title=first_title)
                                else:
                                    pane.set_tab_locked(0, False)

                            for t in tabs[1:]:
                                t_path = t.get("path") if isinstance(t, dict) else t
                                t_locked = t.get("locked", False) if isinstance(t, dict) else False
                                t_root = t.get("root_path") if isinstance(t, dict) else None
                                t_title = t.get("original_title") if isinstance(t, dict) else None
                                if t_path and os.path.isdir(t_path):
                                    pane.add_tab(t_path, locked=t_locked, root_path=t_root, original_title=t_title)
                        elif "current_path" in p_info:
                            pane.navigate_to(p_info["current_path"], record_history=False)

                        # Restaura larguras das colunas
                        col_widths = p_info.get("column_widths")
                        if col_widths and isinstance(col_widths, list):
                            pane.set_column_widths(col_widths)

                tree_mode = data.get("tree_mode", 0)
                self.combo_tree.setCurrentIndex(tree_mode)
                self.layout_manager.set_tree_mode(tree_mode)

                # Re-aplica larguras salvas dos splitters de árvore após o layout estabilizar na tela
                QTimer.singleShot(50, self._restore_splitter_widths)
                return
            except Exception as e:
                print(f"Erro ao carregar configurações do QDir: {e}")

        # Fallback se não houver settings.json: tenta start.qdr original
        start_qdr = os.path.join(os.path.dirname(__file__), "..", "Q-Dir Windows", "start.qdr")
        if os.path.exists(start_qdr):
            self.load_session_qdr(start_qdr)

    def _restore_splitter_widths(self):
        """Garante que as larguras salvas dos divisores da árvore sejam reaplicadas após renderização completa."""
        if self.layout_manager.is_pane_maximized():
            return
        if self.layout_manager.current_tree_mode == 2 and not self.layout_manager.shared_tree.isHidden():
            w = self.layout_manager.shared_tree_width
            total = self.layout_manager.outer_splitter.width()
            if total > w and w > 0:
                self.layout_manager.outer_splitter.setSizes([w, total - w])
        elif self.layout_manager.current_tree_mode == 1:
            for p in self.panes:
                if not p.tree_view.isHidden():
                    w = p.tree_width
                    total = p.inner_splitter.width()
                    if total > w and w > 0:
                        p.inner_splitter.setSizes([w, total - w])

    def show_color_rules(self):
        """Abre diálogo para editar, adicionar, remover e reordenar regras de cores."""
        def on_apply():
            for p in self.panes:
                p.table_view.viewport().update()

        dlg = ColorRulesDialog(self.color_engine, on_apply=on_apply, parent=self)
        dlg.exec()

    def closeEvent(self, event):
        """Salva larguras de colunas e estado geral ao fechar a aplicação."""
        self.save_settings()
        event.accept()

    def show_about(self):
        text = """<h2>QDir Linux 1.0</h2>
<p>Gerenciador de arquivos Quad Explorer para Linux.</p>
<p>Inspirado e baseado na engenharia reversa do <b>Q-Dir</b> para Windows (de Nenad Hrg / SoftwareOK.com).</p>
<ul>
  <li>12 modos de layout dinâmicos com splitters flexíveis</li>
  <li>4 painéis independentes com abas, busca e navegação</li>
  <li>Coloração inteligente de arquivos por extensão (Filter2)</li>
  <li>Exibição direta de extensões (.exe, .json, .txt, etc.)</li>
  <li>Persistência automática de larguras de colunas ao fechar</li>
  <li>Filtros em tempo real (positivos e negativos)</li>
  <li>Drag & Drop inter-painéis nativo</li>
  <li>Exportação para TXT, CSV e HTML</li>
  <li>Compatibilidade com arquivos de sessão .qdr</li>
</ul>
<p>Desenvolvido em Python 3.12 com PyQt6.</p>"""
        QMessageBox.about(self, "Sobre o QDir Linux", text)
