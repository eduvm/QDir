"""
QDirPane - Componente de Painel de Navegação do QDir.
Encapsula abas, barra de navegação, visualização de arquivos em tabela,
árvore de pastas sincronizada, filtro em tempo real (positivo/negativo),
coloração por regras e suporte a drag & drop entre painéis.
"""

import fnmatch
import os
from typing import List, Optional

from PyQt6.QtCore import (
    QDir,
    QItemSelection,
    QModelIndex,
    QPoint,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QDrag,
    QFileSystemModel,
    QIcon,
    QKeySequence,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStyle,
    QTabBar,
    QTabWidget,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from qdir.clipboard_manager import QDirClipboard
from qdir.color_engine import ColorEngine, QDirColorDelegate
from qdir.ui_icons import get_ui_icon
from qdir.file_ops import (
    BatchRenameDialog,
    copy_or_move_items,
    delete_items_permanently,
    open_file_default,
    open_in_terminal,
    trash_items,
)


class QDirFilterProxyModel(QSortFilterProxyModel):
    """Proxy model com suporte a filtro positivo e filtro negativo (wildcards)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.positive_patterns: List[str] = []
        self.negative_patterns: List[str] = []
        self.show_hidden: bool = False
        self.setDynamicSortFilter(True)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.sort(0, Qt.SortOrder.AscendingOrder)

    def set_filters(self, positive_str: str, negative_str: str, show_hidden: bool):
        self.positive_patterns = [p.strip().lower() for p in positive_str.replace(",", ";").split(";") if p.strip()]
        self.negative_patterns = [p.strip().lower() for p in negative_str.replace(",", ";").split(";") if p.strip()]
        self.show_hidden = show_hidden
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        source_model: QFileSystemModel = self.sourceModel()
        index = source_model.index(source_row, 0, source_parent)
        filename = source_model.fileName(index)

        # '..' representa a pasta pai e deve sempre ser exibido no topo (exceto na raiz '/')
        if filename == "..":
            parent_path = source_model.filePath(source_parent)
            return bool(parent_path) and parent_path != "/"

        is_dir = source_model.isDir(index)

        # Oculta arquivos ocultos se desmarcado
        if not self.show_hidden and filename.startswith("."):
            return False

        # Diretórios sempre são aceitos para permitir navegação
        if is_dir:
            return True

        lower_name = filename.lower()

        # Verifica filtro negativo
        for neg in self.negative_patterns:
            if fnmatch.fnmatch(lower_name, neg):
                return False

        # Verifica filtro positivo (se houver regras)
        if self.positive_patterns:
            matched = any(fnmatch.fnmatch(lower_name, pos) for pos in self.positive_patterns)
            if not matched:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        sm: QFileSystemModel = self.sourceModel()
        nl = sm.fileName(left.siblingAtColumn(0))
        nr = sm.fileName(right.siblingAtColumn(0))

        # '..' fica SEMPRE fixo na parte de cima de cada painel (linha 0)
        if nl == "..":
            return self.sortOrder() == Qt.SortOrder.AscendingOrder
        if nr == "..":
            return self.sortOrder() != Qt.SortOrder.AscendingOrder

        # Pastas sempre antes de arquivos
        is_dir_left = sm.isDir(left.siblingAtColumn(0))
        is_dir_right = sm.isDir(right.siblingAtColumn(0))
        if is_dir_left != is_dir_right:
            if self.sortOrder() == Qt.SortOrder.AscendingOrder:
                return is_dir_left
            else:
                return not is_dir_left

        return super().lessThan(left, right)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        src_index = self.mapToSource(index).siblingAtColumn(0)
        src_model: QFileSystemModel = self.sourceModel()
        filename = src_model.fileName(src_index)

        # Para '..', exibe apenas o identificador na coluna 0 e limpa metadados
        if filename == "..":
            if role == Qt.ItemDataRole.DisplayRole:
                if index.column() == 0:
                    return ".."
                return ""
            return super().data(index, role)

        # Na coluna 2 (Tipo), retorna a extensão real do arquivo (.exe, .json, .txt, etc.)
        if role == Qt.ItemDataRole.DisplayRole and index.column() == 2:
            if src_model.isDir(src_index):
                return ""
            _, ext = os.path.splitext(filename)
            return ext.lower() if ext else ""
        return super().data(index, role)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == 0:
                return "Nome"
            elif section == 1:
                return "Tamanho"
            elif section == 2:
                return "Extensão"
            elif section == 3:
                return "Data de Modificação"
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):
        default_flags = super().flags(index)
        if not index.isValid():
            return default_flags

        if index.column() == 0:
            src_index = self.mapToSource(index)
            sm: QFileSystemModel = self.sourceModel()
            if sm and sm.fileName(src_index.siblingAtColumn(0)) == "..":
                return default_flags & ~Qt.ItemFlag.ItemIsEditable
            return default_flags | Qt.ItemFlag.ItemIsEditable
        else:
            return default_flags & ~Qt.ItemFlag.ItemIsEditable


class DroppableTabBar(QTabBar):
    """Barra de abas com suporte a Drag & Drop, alternância automática no hover e fechamento por botão do meio."""

    def __init__(self, pane: "QDirPane", parent=None):
        super().__init__(parent)
        self.pane = pane
        self.setAcceptDrops(True)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDrawBase(False)
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(400)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._hover_tab_idx = -1

    def _on_hover_timeout(self):
        if 0 <= self._hover_tab_idx < self.count():
            self.setCurrentIndex(self._hover_tab_idx)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            tab_idx = self.tabAt(event.position().toPoint())
            if tab_idx >= 0:
                self.pane.on_tab_close(tab_idx)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            pos = event.position().toPoint()
            tab_idx = self.tabAt(pos)
            if tab_idx >= 0 and tab_idx != self.currentIndex():
                if self._hover_tab_idx != tab_idx:
                    self._hover_tab_idx = tab_idx
                    self._hover_timer.start()
            else:
                self._hover_timer.stop()
                self._hover_tab_idx = -1
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._hover_timer.stop()
        self._hover_tab_idx = -1
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._hover_timer.stop()
        self._hover_tab_idx = -1
        if event.mimeData().hasUrls():
            pos = event.position().toPoint()
            tab_idx = self.tabAt(pos)
            target_dir = self.pane.current_path
            if tab_idx >= 0:
                tip = self.tabToolTip(tab_idx)
                if tip and os.path.isdir(tip):
                    target_dir = tip

            urls = event.mimeData().urls()
            paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
            is_move = (event.dropAction() == Qt.DropAction.MoveAction) or (
                QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            event.acceptProposedAction()
            # Postpone handling until after dropEvent finishes and QDrag releases pointer grab
            QTimer.singleShot(0, lambda: self.pane.handle_files_dropped(paths, target_dir, is_move))
        else:
            super().dropEvent(event)


class FileTableView(QTableView):
    """Tabela de arquivos com suporte a Drag & Drop e clique duplo."""

    files_dropped = pyqtSignal(list, str, bool)  # src_paths, dst_dir, is_move
    pane_focused = pyqtSignal()

    def __init__(self, pane: "QDirPane", parent=None):
        super().__init__(parent)
        self.pane = pane
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(True)

        # Configurações de Drag and Drop
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)

        # Larguras padrão iniciais equilibradas
        self.setColumnWidth(0, 220)
        self.setColumnWidth(1, 90)
        self.setColumnWidth(2, 100)
        self.setColumnWidth(3, 140)

        self.doubleClicked.connect(self.on_double_click)

    def get_column_widths(self) -> list:
        return [self.columnWidth(c) for c in range(4)]

    def set_column_widths(self, widths: list):
        for c, w in enumerate(widths):
            if c < 4 and isinstance(w, int) and w > 20:
                self.setColumnWidth(c, w)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.pane_focused.emit()

    def selectAll(self):
        super().selectAll()
        # Garante que '..' (linha 0) nunca seja incluído na seleção total
        proxy: QDirFilterProxyModel = self.model()
        root_idx = self.rootIndex()
        if proxy and proxy.rowCount(root_idx) > 0:
            first_idx = proxy.index(0, 0, root_idx)
            src_idx = proxy.mapToSource(first_idx)
            if self.pane.fs_model.fileName(src_idx.siblingAtColumn(0)) == "..":
                sel_range = QItemSelection(
                    proxy.index(0, 0, root_idx),
                    proxy.index(0, proxy.columnCount(root_idx) - 1, root_idx),
                )
                self.selectionModel().select(sel_range, self.selectionModel().SelectionFlag.Deselect)

    def rename_current_inline(self):
        # Se um editor inline já estiver aberto, avança o ciclo de seleção no F2
        from qdir.color_engine import RenameLineEdit
        editor = self.viewport().findChild(RenameLineEdit)
        if editor is not None and editor.isVisible():
            editor.next_cycle()
            return

        curr = self.currentIndex()
        if not curr.isValid():
            selected = self.selectionModel().selectedRows()
            if selected:
                curr = selected[0]
            else:
                return

        name_idx = curr.siblingAtColumn(0)
        proxy: QDirFilterProxyModel = self.model()
        src_idx = proxy.mapToSource(name_idx)
        if self.pane.fs_model.fileName(src_idx.siblingAtColumn(0)) == "..":
            return

        self.setCurrentIndex(name_idx)
        self.edit(name_idx)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.pane_focused.emit()

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)

        if ctrl and key == Qt.Key.Key_C:
            self.pane.copy_selection()
            event.accept()
            return

        elif ctrl and key == Qt.Key.Key_X:
            self.pane.cut_selection()
            event.accept()
            return

        elif ctrl and key == Qt.Key.Key_V:
            self.pane.paste_clipboard()
            event.accept()
            return

        elif ctrl and key == Qt.Key.Key_A:
            self.selectAll()
            event.accept()
            return

        elif key == Qt.Key.Key_F2:
            self.rename_current_inline()
            event.accept()
            return

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            selected = self.selectionModel().selectedRows()
            if selected:
                self.on_double_click(selected[0])
                event.accept()
                return
            elif self.currentIndex().isValid():
                self.on_double_click(self.currentIndex())
                event.accept()
                return

        elif key == Qt.Key.Key_Backspace:
            self.pane.go_up()
            event.accept()
            return

        elif key == Qt.Key.Key_Delete:
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                self.pane.delete_permanently()
            else:
                self.pane.delete_to_trash()
            event.accept()
            return

        super().keyPressEvent(event)

    def on_double_click(self, index: QModelIndex):
        if not index.isValid():
            return
        proxy: QDirFilterProxyModel = self.model()
        src_index = proxy.mapToSource(index).siblingAtColumn(0)
        fs_model: QFileSystemModel = proxy.sourceModel()
        filename = fs_model.fileName(src_index)

        if filename == "..":
            self.pane.go_up()
            return

        path = fs_model.filePath(src_index)
        if fs_model.isDir(src_index):
            self.pane.navigate_to(path)
        else:
            open_file_default(path)

    def startDrag(self, supportedActions):
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return

        proxy: QDirFilterProxyModel = self.model()
        fs_model: QFileSystemModel = proxy.sourceModel()
        urls = []
        valid_src_indexes = []
        for idx in indexes:
            src_idx = proxy.mapToSource(idx)
            if fs_model.fileName(src_idx.siblingAtColumn(0)) == "..":
                continue
            path = fs_model.filePath(src_idx)
            if path and os.path.basename(path) != "..":
                valid_src_indexes.append(src_idx)
                urls.append(QUrl.fromLocalFile(path))

        if urls:
            drag = QDrag(self)
            mime_data = self.pane.fs_model.mimeData(valid_src_indexes)
            mime_data.setUrls(urls)
            drag.setMimeData(mime_data)
            drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
            target_dir = self.pane.current_path

            # Verifica se o drop foi em cima de uma subpasta
            pos = event.position().toPoint()
            drop_index = self.indexAt(pos)
            if drop_index.isValid():
                proxy: QDirFilterProxyModel = self.model()
                src_index = proxy.mapToSource(drop_index)
                if self.pane.fs_model.isDir(src_index):
                    sub_path = self.pane.fs_model.filePath(src_index)
                    if sub_path and os.path.isdir(sub_path):
                        target_dir = sub_path

            is_move = (event.dropAction() == Qt.DropAction.MoveAction) or (
                QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            event.acceptProposedAction()
            # Postpone handling until after dropEvent finishes and QDrag releases pointer grab
            QTimer.singleShot(0, lambda: self.pane.handle_files_dropped(paths, target_dir, is_move))
        else:
            super().dropEvent(event)


class QDirPane(QFrame):
    """Painel de navegação autônomo com abas, splitters internos e controle de estado."""

    activated = pyqtSignal(object)  # Emite self quando ativado
    path_changed = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, pane_id: int, color_engine: ColorEngine, parent=None):
        super().__init__(parent)
        self.pane_id = pane_id
        self.color_engine = color_engine
        self.current_path: str = os.path.expanduser("~")
        self.history: List[str] = [self.current_path]
        self.history_index: int = 0
        self.is_active: bool = False

        # Configuração visual do Frame do Painel
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setObjectName(f"QDirPane_{pane_id}")

        self._build_ui()
        self.set_active(False)
        self.navigate_to(self.current_path)

        # Atualiza itens atenuados quando o estado de recorte mudar
        QDirClipboard.clipboard_changed.connect(lambda: self.table_view.viewport().update())

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        # 1. Barra de Navegação e Endereço
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(2)

        # Rótulo de identificação do painel (#1, #2, #3, #4)
        self.lbl_id = QLabel(f"#{self.pane_id}")
        self.lbl_id.setStyleSheet("font-weight: bold; padding: 0 4px;")
        nav_layout.addWidget(self.lbl_id)

        # Botões de Navegação
        self.btn_back = QPushButton()
        self.btn_back.setIcon(get_ui_icon("back"))
        self.btn_back.setIconSize(QSize(16, 16))
        self.btn_back.setToolTip("Voltar (Alt+Esquerda)")
        self.btn_back.setFixedWidth(28)
        self.btn_back.clicked.connect(self.go_back)
        nav_layout.addWidget(self.btn_back)

        self.btn_fwd = QPushButton()
        self.btn_fwd.setIcon(get_ui_icon("fwd"))
        self.btn_fwd.setIconSize(QSize(16, 16))
        self.btn_fwd.setToolTip("Avançar (Alt+Direita)")
        self.btn_fwd.setFixedWidth(28)
        self.btn_fwd.clicked.connect(self.go_forward)
        nav_layout.addWidget(self.btn_fwd)

        self.btn_up = QPushButton()
        self.btn_up.setIcon(get_ui_icon("up"))
        self.btn_up.setIconSize(QSize(16, 16))
        self.btn_up.setToolTip("Subir pasta (Alt+Cima)")
        self.btn_up.setFixedWidth(28)
        self.btn_up.clicked.connect(self.go_up)
        nav_layout.addWidget(self.btn_up)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setIcon(get_ui_icon("refresh"))
        self.btn_refresh.setIconSize(QSize(16, 16))
        self.btn_refresh.setToolTip("Atualizar (F5)")
        self.btn_refresh.setFixedWidth(28)
        self.btn_refresh.clicked.connect(self.refresh)
        nav_layout.addWidget(self.btn_refresh)

        # Barra de Endereço Editável
        self.txt_path = QLineEdit()
        self.txt_path.setPlaceholderText("Caminho do diretório...")
        self.txt_path.returnPressed.connect(self.on_path_entered)
        completer = QCompleter(self)
        completer_model = QFileSystemModel(completer)
        completer_model.setRootPath("")
        completer.setModel(completer_model)
        self.txt_path.setCompleter(completer)
        nav_layout.addWidget(self.txt_path, stretch=1)

        # Botão Terminal
        self.btn_term = QPushButton()
        self.btn_term.setIcon(get_ui_icon("terminal"))
        self.btn_term.setIconSize(QSize(16, 16))
        self.btn_term.setToolTip("Abrir no Terminal")
        self.btn_term.setFixedWidth(28)
        self.btn_term.clicked.connect(lambda: open_in_terminal(self.current_path))
        nav_layout.addWidget(self.btn_term)

        main_layout.addLayout(nav_layout)

        # 2. Barra de Abas
        tab_layout = QHBoxLayout()
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(2)

        self.tabs = DroppableTabBar(self)
        self.tabs.tabCloseRequested.connect(self.on_tab_close)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        tab_layout.addWidget(self.tabs)

        btn_new_tab = QPushButton("+")
        btn_new_tab.setFixedSize(22, 22)
        btn_new_tab.setToolTip("Nova Aba")
        btn_new_tab.setStyleSheet("font-weight: bold; font-size: 13px; padding: 0;")
        btn_new_tab.clicked.connect(lambda: self.add_tab(self.current_path))
        tab_layout.addWidget(btn_new_tab)
        tab_layout.addStretch()

        main_layout.addLayout(tab_layout)

        # 3. Modelos de Arquivos
        self.fs_model = QFileSystemModel()
        self.fs_model.setReadOnly(False)
        self.fs_model.setRootPath("")
        self.fs_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDot | QDir.Filter.Hidden)

        self.proxy_model = QDirFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.fs_model)

        # Divisor interno (Árvore de Pastas + Tabela de Arquivos)
        self.inner_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Árvore de Diretórios (Opcional/Colapsável)
        self.tree_view = QTreeView()
        self.tree_model = QFileSystemModel()
        self.tree_model.setRootPath("")
        self.tree_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.tree_view.setModel(self.tree_model)
        self.tree_view.setHeaderHidden(True)
        for c in range(1, 4):
            self.tree_view.setColumnHidden(c, True)
        self.tree_view.clicked.connect(self.on_tree_clicked)
        self.inner_splitter.addWidget(self.tree_view)
        self.tree_view.hide()  # Inicia oculto conforme padrão sem árvore

        # Tabela de Arquivos
        self.table_view = FileTableView(self)
        self.table_view.setModel(self.proxy_model)
        self.table_view.setItemDelegate(QDirColorDelegate(self.color_engine, self.table_view))
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.show_context_menu)
        self.table_view.files_dropped.connect(self.handle_files_dropped)
        self.table_view.pane_focused.connect(self.set_focused)
        self.table_view.selectionModel().selectionChanged.connect(self.on_selection_changed)

        self.inner_splitter.addWidget(self.table_view)
        self.inner_splitter.setStretchFactor(0, 0)
        self.inner_splitter.setStretchFactor(1, 1)

        main_layout.addWidget(self.inner_splitter, stretch=1)

        # Adiciona aba inicial
        tab_name = os.path.basename(self.current_path) or "/"
        idx = self.tabs.addTab(tab_name)
        self.tabs.setTabToolTip(idx, self.current_path)

        # 4. Barra Inferior de Filtros em Tempo Real (Positivo e Negativo)
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(2, 0, 2, 0)
        filter_layout.setSpacing(4)

        lbl_filter = QLabel("Filtro:")
        lbl_filter.setStyleSheet("font-size: 11px;")
        filter_layout.addWidget(lbl_filter)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("ex: *.py;*.png")
        self.txt_filter.setFixedHeight(22)
        self.txt_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.txt_filter, stretch=1)

        lbl_neg = QLabel("Negativo:")
        lbl_neg.setStyleSheet("font-size: 11px;")
        filter_layout.addWidget(lbl_neg)

        self.txt_neg_filter = QLineEdit()
        self.txt_neg_filter.setPlaceholderText("ex: *.bak;*.tmp")
        self.txt_neg_filter.setFixedHeight(22)
        self.txt_neg_filter.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.txt_neg_filter, stretch=1)

        self.chk_hidden = QCheckBox("Ocultos")
        self.chk_hidden.setStyleSheet("font-size: 11px;")
        self.chk_hidden.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.chk_hidden)

        main_layout.addLayout(filter_layout)

    def set_focused(self):
        self.activated.emit(self)

    def set_active(self, active: bool):
        self.is_active = active
        if active:
            self.setStyleSheet(
                f"#QDirPane_{self.pane_id} {{ border: 2px solid #0078d7; border-radius: 4px; }}"
            )
            self.lbl_id.setStyleSheet("font-weight: bold; color: #0078d7; background: rgba(0, 120, 215, 0.2); border-radius: 3px; padding: 1px 6px;")
        else:
            self.setStyleSheet(
                f"#QDirPane_{self.pane_id} {{ border: 1px solid rgba(128, 128, 128, 0.3); border-radius: 4px; }}"
            )
            self.lbl_id.setStyleSheet("font-weight: normal; color: palette(window-text); padding: 1px 6px;")

    def navigate_to(self, path: str, record_history: bool = True):
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(path) or not os.path.isdir(path):
            return

        self.current_path = path
        self.txt_path.setText(path)

        src_index = self.fs_model.setRootPath(path)
        proxy_index = self.proxy_model.mapFromSource(src_index)
        self.table_view.setRootIndex(proxy_index)

        # Atualiza título da aba corrente
        cur_tab = self.tabs.currentIndex()
        if cur_tab >= 0:
            tab_name = os.path.basename(path) or "/"
            self.tabs.setTabText(cur_tab, tab_name)
            self.tabs.setTabToolTip(cur_tab, path)

        if record_history:
            if not self.history or self.history[self.history_index] != path:
                self.history = self.history[: self.history_index + 1]
                self.history.append(path)
                self.history_index = len(self.history) - 1

        self.btn_back.setEnabled(self.history_index > 0)
        self.btn_fwd.setEnabled(self.history_index < len(self.history) - 1)

        # Sincroniza a árvore se estiver visível
        if self.tree_view.isVisible():
            tree_idx = self.tree_model.index(path)
            self.tree_view.setCurrentIndex(tree_idx)
            self.tree_view.scrollTo(tree_idx)

        self.path_changed.emit(path)
        self.update_status()

    def go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.navigate_to(self.history[self.history_index], record_history=False)

    def go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.navigate_to(self.history[self.history_index], record_history=False)

    def go_up(self):
        parent_dir = os.path.dirname(self.current_path)
        if parent_dir and parent_dir != self.current_path:
            self.navigate_to(parent_dir)

    def refresh(self):
        self.fs_model.setRootPath("")
        self.navigate_to(self.current_path, record_history=False)

    def on_path_entered(self):
        entered = self.txt_path.text().strip()
        if entered and os.path.isdir(os.path.expanduser(entered)):
            self.navigate_to(entered)
        else:
            self.txt_path.setText(self.current_path)

    def on_tree_clicked(self, index: QModelIndex):
        if index.isValid():
            path = self.tree_model.filePath(index)
            self.navigate_to(path)

    def apply_filters(self):
        pos_text = self.txt_filter.text()
        neg_text = self.txt_neg_filter.text()
        show_hidden = self.chk_hidden.isChecked()
        self.proxy_model.set_filters(pos_text, neg_text, show_hidden)
        self.update_status()

    def set_tree_visible(self, visible: bool):
        self.tree_view.setVisible(visible)
        if visible:
            for col in range(1, 4):
                self.tree_view.setColumnHidden(col, True)
            self.inner_splitter.setSizes([160, 450])
            tree_idx = self.tree_model.index(self.current_path)
            self.tree_view.setCurrentIndex(tree_idx)
            self.tree_view.scrollTo(tree_idx)

    # Gerenciamento de Abas
    def add_tab(self, path: Optional[str] = None):
        target_path = os.path.abspath(os.path.expanduser(path or self.current_path))
        tab_name = os.path.basename(target_path) or "/"
        idx = self.tabs.addTab(tab_name)
        self.tabs.setTabToolTip(idx, target_path)
        self.tabs.setCurrentIndex(idx)
        self.navigate_to(target_path)

    def on_tab_close(self, index: int):
        if self.tabs.count() > 1:
            self.tabs.removeTab(index)
            cur_idx = self.tabs.currentIndex()
            if 0 <= cur_idx < self.tabs.count():
                tab_path = self.tabs.tabToolTip(cur_idx)
                if tab_path and os.path.isdir(tab_path):
                    self.navigate_to(tab_path, record_history=False)

    def on_tab_changed(self, index: int):
        if 0 <= index < self.tabs.count():
            tab_path = self.tabs.tabToolTip(index)
            if tab_path and os.path.isdir(tab_path) and tab_path != self.current_path:
                self.navigate_to(tab_path, record_history=False)

    def get_column_widths(self) -> list:
        return self.table_view.get_column_widths()

    def set_column_widths(self, widths: list):
        self.table_view.set_column_widths(widths)

    # Seleção e Status
    def get_selected_paths(self) -> List[str]:
        indexes = self.table_view.selectionModel().selectedRows()
        paths = []
        for idx in indexes:
            src_idx = self.proxy_model.mapToSource(idx)
            fn = self.fs_model.fileName(src_idx.siblingAtColumn(0))
            if fn == "..":
                continue
            path = self.fs_model.filePath(src_idx)
            if path and os.path.basename(path) != "..":
                paths.append(path)
        return paths

    def on_selection_changed(self):
        self.update_status()

    def update_status(self):
        total_items = self.proxy_model.rowCount()
        # Não contabiliza '..' no total de itens da pasta
        if self.current_path != "/" and total_items > 0:
            total_items = max(0, total_items - 1)

        selected = self.get_selected_paths()
        sel_count = len(selected)

        total_bytes = 0
        for p in selected:
            try:
                if os.path.isfile(p):
                    total_bytes += os.path.getsize(p)
            except Exception:
                pass

        size_str = f" ({total_bytes:,} bytes)" if total_bytes > 0 else ""
        status = f"Painel #{self.pane_id}: {total_items} itens | {sel_count} selecionados{size_str}"
        self.status_updated.emit(status)

    # Drag & Drop Inter-painéis e entre abas
    def handle_files_dropped(self, src_paths: List[str], dst_dir: str, is_move: bool):
        if not src_paths:
            return

        dst_dir = os.path.abspath(dst_dir)
        valid_srcs = [os.path.abspath(p) for p in src_paths if os.path.exists(p)]
        if not valid_srcs:
            return

        # Se a origem e o destino forem o mesmo diretório, ignora a operação
        if all(os.path.dirname(p) == dst_dir for p in valid_srcs):
            return

        action_name = "Mover" if is_move else "Copiar"

        # Constrói o diálogo com parent no topo da janela para liberar pointer grab e manter foco
        msg_box = QMessageBox(self.window())
        msg_box.setWindowTitle(f"Confirmar {action_name}")
        if len(valid_srcs) == 1:
            item_name = os.path.basename(valid_srcs[0])
            msg_box.setText(f"Deseja {action_name.lower()} o item '{item_name}' para:\n{dst_dir}?")
        else:
            msg_box.setText(f"Deseja {action_name.lower()} {len(valid_srcs)} itens para:\n{dst_dir}?")

        msg_box.setIcon(QMessageBox.Icon.Question)
        btn_yes = msg_box.addButton("Sim", QMessageBox.ButtonRole.YesRole)
        btn_no = msg_box.addButton("Não", QMessageBox.ButtonRole.NoRole)
        msg_box.setDefaultButton(btn_yes)
        msg_box.setEscapeButton(btn_no)

        msg_box.exec()

        if msg_box.clickedButton() == btn_yes:
            count, errors = copy_or_move_items(valid_srcs, dst_dir, is_move, parent=self.window())
            if errors:
                QMessageBox.warning(self.window(), "Erros na Operação", "\n".join(errors))
            self.refresh()

    # Menu de Contexto
    def show_context_menu(self, pos: QPoint):
        self.set_focused()
        selected = self.get_selected_paths()
        menu = QMenu(self)

        act_open = menu.addAction("Abrir")
        act_open.triggered.connect(lambda: [open_file_default(p) for p in selected] if selected else None)

        act_term = menu.addAction("Abrir no Terminal")
        target_dir = selected[0] if (selected and os.path.isdir(selected[0])) else self.current_path
        act_term.triggered.connect(lambda: open_in_terminal(target_dir))

        menu.addSeparator()

        has_valid_selection = bool(selected) and not any(os.path.basename(p) == ".." for p in selected)

        act_cut = menu.addAction("Recortar")
        act_cut.setShortcut(QKeySequence("Ctrl+X"))
        act_cut.setEnabled(has_valid_selection)
        act_cut.triggered.connect(self.cut_selection)

        act_copy = menu.addAction("Copiar")
        act_copy.setShortcut(QKeySequence("Ctrl+C"))
        act_copy.setEnabled(has_valid_selection)
        act_copy.triggered.connect(self.copy_selection)

        act_paste = menu.addAction("Colar")
        act_paste.setShortcut(QKeySequence("Ctrl+V"))
        act_paste.setEnabled(QDirClipboard.has_files())
        act_paste.triggered.connect(self.paste_clipboard)

        menu.addSeparator()

        act_rename = menu.addAction("Renomear (F2)")
        act_rename.setEnabled(len(selected) == 1)
        act_rename.triggered.connect(self.rename_single)

        act_batch = menu.addAction("Renomeação em Lote...")
        act_batch.setEnabled(len(selected) > 1)
        act_batch.triggered.connect(lambda: BatchRenameDialog(selected, self).exec())

        menu.addSeparator()

        act_trash = menu.addAction("Mover para Lixeira (Delete)")
        act_trash.setEnabled(bool(selected))
        act_trash.triggered.connect(self.delete_to_trash)

        act_delete = menu.addAction("Excluir Permanentemente (Shift+Delete)")
        act_delete.setEnabled(bool(selected))
        act_delete.triggered.connect(self.delete_permanently)

        menu.addSeparator()

        act_new_folder = menu.addAction("Nova Pasta")
        act_new_folder.triggered.connect(self.create_new_folder)

        act_new_file = menu.addAction("Novo Arquivo")
        act_new_file.triggered.connect(self.create_new_file)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    # Operações de Área de Transferência (Clipboard)
    def copy_selection(self):
        paths = self.get_selected_paths()
        valid = [p for p in paths if os.path.exists(p) and os.path.basename(p) != ".."]
        if not valid:
            return
        QDirClipboard.copy(valid)
        self.status_updated.emit(f"Painel #{self.pane_id}: {len(valid)} item(ns) copiado(s).")

    def cut_selection(self):
        paths = self.get_selected_paths()
        valid = [p for p in paths if os.path.exists(p) and os.path.basename(p) != ".."]
        if not valid:
            return
        QDirClipboard.cut(valid)
        self.status_updated.emit(f"Painel #{self.pane_id}: {len(valid)} item(ns) recortado(s). Pressione Ctrl+V no destino.")

    def paste_clipboard(self):
        paths, is_move = QDirClipboard.get_files()
        if not paths:
            self.status_updated.emit(f"Painel #{self.pane_id}: Área de transferência vazia.")
            return

        target_dir = os.path.abspath(self.current_path)

        if is_move and all(os.path.dirname(os.path.abspath(p)) == target_dir for p in paths):
            self.status_updated.emit(f"Painel #{self.pane_id}: Origem e destino são a mesma pasta.")
            return

        action_name = "Mover" if is_move else "Copiar"
        count, errors = copy_or_move_items(paths, target_dir, is_move=is_move, parent=self.window())
        if errors:
            QMessageBox.warning(self.window(), f"Erros ao {action_name}", "\n".join(errors))

        if is_move:
            QDirClipboard.clear_cut()
            QApplication.clipboard().clear()

        win = self.window()
        if hasattr(win, "refresh_all_panes"):
            win.refresh_all_panes()
        else:
            self.refresh()

        self.status_updated.emit(f"Painel #{self.pane_id}: {count} item(ns) {'movido(s)' if is_move else 'copiado(s)'} com sucesso.")

    def rename_single(self):
        self.table_view.rename_current_inline()

    def delete_to_trash(self):
        selected = self.get_selected_paths()
        if not selected:
            return
        reply = QMessageBox.question(
            self,
            "Mover para Lixeira",
            f"Mover {len(selected)} item(ns) para a lixeira?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count, errors = trash_items(selected)
            if errors:
                QMessageBox.warning(self, "Aviso", "\n".join(errors))
            self.refresh()

    def delete_permanently(self):
        selected = self.get_selected_paths()
        if not selected:
            return
        reply = QMessageBox.warning(
            self,
            "Excluir Permanentemente",
            f"Tem certeza que deseja EXCLUIR PERMANENTEMENTE {len(selected)} item(ns)?\nEsta ação NÃO pode ser desfeita.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            count, errors = delete_items_permanently(selected)
            if errors:
                QMessageBox.warning(self, "Aviso", "\n".join(errors))
            self.refresh()

    def create_new_folder(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Nova Pasta", "Nome da pasta:")
        if ok and name:
            new_dir = os.path.join(self.current_path, name)
            try:
                os.makedirs(new_dir, exist_ok=False)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível criar a pasta: {e}")

    def create_new_file(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Novo Arquivo", "Nome do arquivo:")
        if ok and name:
            new_file = os.path.join(self.current_path, name)
            try:
                with open(new_file, "w", encoding="utf-8") as f:
                    f.write("")
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Não foi possível criar o arquivo: {e}")
