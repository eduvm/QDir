"""
Diálogo 'Abrir com...' do QDir Linux.
Permite selecionar um aplicativo recomendado ou geral do sistema para abrir arquivos,
além de oferecer opção para definir o aplicativo escolhido como padrão (persistente).
"""

import os
from typing import List, Optional, Union

from PyQt6.QtCore import QFileInfo, Qt
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qdir.mime_manager import DesktopApp, MimeManager


class OpenWithDialog(QDialog):
    """Diálogo de seleção de aplicativo 'Abrir com...' com suporte a definição de padrão."""

    def __init__(self, filepaths: List[str], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.filepaths = [os.path.abspath(p) for p in filepaths if os.path.exists(p)]
        if not self.filepaths:
            raise ValueError("Nenhum arquivo válido fornecido para o diálogo.")

        self.primary_file = self.filepaths[0]
        self.mime_type, self.mime_desc = MimeManager.get_mime_type(self.primary_file)
        _, ext = os.path.splitext(self.primary_file)
        self.ext = ext.lower() if ext else ""

        self.setWindowTitle("Abrir com...")
        self.resize(540, 600)
        self.setMinimumSize(460, 480)

        self._build_ui()
        self._populate_apps()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Cabeçalho de informações do arquivo
        header_frame = QFrame(self)
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(14)

        # Ícone do arquivo
        icon_provider = QFileIconProvider()
        file_icon = icon_provider.icon(QFileInfo(self.primary_file))
        lbl_icon = QLabel()
        lbl_icon.setPixmap(file_icon.pixmap(48, 48))
        lbl_icon.setFixedSize(48, 48)
        header_layout.addWidget(lbl_icon)

        # Textos de identificação
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        if len(self.filepaths) == 1:
            lbl_filename = QLabel(os.path.basename(self.primary_file))
            lbl_filename.setToolTip(self.primary_file)
        else:
            lbl_filename = QLabel(f"{len(self.filepaths)} arquivos selecionados ({os.path.basename(self.primary_file)}, ...)")

        f = lbl_filename.font()
        f.setBold(True)
        f.setPointSize(f.pointSize() + 1)
        lbl_filename.setFont(f)

        ext_label = f" ({self.ext})" if self.ext else ""
        desc_label = self.mime_desc if self.mime_desc else self.mime_type
        lbl_mimetype = QLabel(f"Tipo: {desc_label}{ext_label} • {self.mime_type}")
        lbl_mimetype.setStyleSheet("opacity: 0.8; font-size: 11px;")

        info_layout.addWidget(lbl_filename)
        info_layout.addWidget(lbl_mimetype)
        header_layout.addLayout(info_layout, 1)

        layout.addWidget(header_frame)

        # 2. Barra de pesquisa/filtro
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("Pesquisar aplicativo...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_apps)
        layout.addWidget(self.search_input)

        # 3. Lista em Árvore com Categorias
        self.tree_apps = QTreeWidget(self)
        self.tree_apps.setHeaderHidden(True)
        self.tree_apps.setIndentation(16)
        self.tree_apps.setAnimated(True)
        self.tree_apps.setIconSize(self.tree_apps.iconSize().expandedTo(self.tree_apps.iconSize()))
        self.tree_apps.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree_apps.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree_apps.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_apps, 1)

        # 4. Botão para procurar outro executável personalizado
        btn_layout = QHBoxLayout()
        self.btn_browse = QPushButton("Procurar outro executável...", self)
        self.btn_browse.clicked.connect(self._browse_custom_executable)
        btn_layout.addWidget(self.btn_browse)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 5. Checkbox "Definir como aplicativo padrão"
        chk_text = f"Sempre usar este aplicativo para abrir arquivos {self.ext}" if self.ext else "Definir como aplicativo padrão para este tipo de arquivo"
        self.chk_default = QCheckBox(chk_text, self)
        f_chk = self.chk_default.font()
        f_chk.setBold(True)
        self.chk_default.setFont(f_chk)
        layout.addWidget(self.chk_default)

        # 6. Botões de Ação
        self.button_box = QDialogButtonBox(self)
        self.btn_open = self.button_box.addButton("Abrir", QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = self.button_box.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        self.btn_open.setDefault(True)
        self.btn_open.setEnabled(False)

        self.btn_open.clicked.connect(self.accept_open)
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate_apps(self):
        """Preenche as categorias de aplicativos recomendados e gerais."""
        self.tree_apps.clear()

        # Categoria 1: Recomendados
        self.group_rec = QTreeWidgetItem(self.tree_apps, ["Aplicativos recomendados"])
        f_rec = self.group_rec.font(0)
        f_rec.setBold(True)
        self.group_rec.setFont(0, f_rec)
        self.group_rec.setFlags(Qt.ItemFlag.ItemIsEnabled)

        recommended_apps = MimeManager.get_apps_for_file(self.primary_file)
        rec_ids = set()

        first_item = None
        for app in recommended_apps:
            rec_ids.add(app.desktop_id)
            item = self._create_app_item(self.group_rec, app)
            if app.is_default and not first_item:
                first_item = item

        # Categoria 2: Outros Aplicativos
        self.group_other = QTreeWidgetItem(self.tree_apps, ["Outros aplicativos"])
        f_other = self.group_other.font(0)
        f_other.setBold(True)
        self.group_other.setFont(0, f_other)
        self.group_other.setFlags(Qt.ItemFlag.ItemIsEnabled)

        all_apps = MimeManager.get_all_installed_apps()
        for app in all_apps:
            if app.desktop_id not in rec_ids:
                self._create_app_item(self.group_other, app)

        self.group_rec.setExpanded(True)
        self.group_other.setExpanded(len(recommended_apps) == 0)

        # Seleciona o aplicativo padrão por padrão (se houver) ou o primeiro recomendado
        if first_item:
            self.tree_apps.setCurrentItem(first_item)
        elif self.group_rec.childCount() > 0:
            self.tree_apps.setCurrentItem(self.group_rec.child(0))

    def _create_app_item(self, parent_item: QTreeWidgetItem, app: DesktopApp) -> QTreeWidgetItem:
        """Cria e formata um QTreeWidgetItem para um DesktopApp."""
        title = app.display_title()
        item = QTreeWidgetItem(parent_item, [title])
        item.setData(0, Qt.ItemDataRole.UserRole, app)
        if app.comment:
            item.setToolTip(0, f"{app.name}\n{app.comment}")
        else:
            item.setToolTip(0, app.name)

        # Ícone do tema
        if app.icon_name:
            icon = QIcon.fromTheme(app.icon_name)
            if not icon.isNull():
                item.setIcon(0, icon)

        if app.is_default:
            f = item.font(0)
            f.setBold(True)
            item.setFont(0, f)

        return item

    def _filter_apps(self, query: str):
        """Filtra os aplicativos de acordo com o texto digitado."""
        query = query.strip().lower()
        has_query = bool(query)

        def match_and_show(group: QTreeWidgetItem) -> int:
            matched_count = 0
            for i in range(group.childCount()):
                child = group.child(i)
                app: Optional[DesktopApp] = child.data(0, Qt.ItemDataRole.UserRole)
                if not app:
                    continue

                text = f"{app.name} {app.comment} {app.desktop_id}".lower()
                matched = (not has_query) or (query in text)
                child.setHidden(not matched)
                if matched:
                    matched_count += 1
            group.setHidden(matched_count == 0)
            if has_query and matched_count > 0:
                group.setExpanded(True)
            return matched_count

        rec_count = match_and_show(self.group_rec)
        other_count = match_and_show(self.group_other)

        # Se não houver recomendados visíveis com a busca, expande outros
        if has_query and other_count > 0 and rec_count == 0:
            self.group_other.setExpanded(True)

    def _on_selection_changed(self):
        """Habilita ou desabilita o botão 'Abrir' conforme a seleção."""
        selected = self.tree_apps.selectedItems()
        if selected:
            app = selected[0].data(0, Qt.ItemDataRole.UserRole)
            self.btn_open.setEnabled(app is not None)
        else:
            self.btn_open.setEnabled(False)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Duplo clique no aplicativo confirma a abertura imediatamente."""
        app = item.data(0, Qt.ItemDataRole.UserRole)
        if app:
            self.accept_open()

    def _browse_custom_executable(self):
        """Abre seletor para escolher um executável arbitrário do sistema."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Executável",
            "/usr/bin",
            "Todos os Arquivos (*)",
        )
        if path and os.path.isfile(path):
            exe_name = os.path.basename(path)
            custom_app = DesktopApp(
                desktop_id=f"custom_{exe_name}",
                name=exe_name,
                exec_cmd=path,
                icon_name="system-run",
                comment=path,
                is_custom=True,
            )
            item = self._create_app_item(self.group_other, custom_app)
            self.group_other.setHidden(False)
            self.group_other.setExpanded(True)
            self.tree_apps.setCurrentItem(item)

    def get_selected_app(self) -> Optional[DesktopApp]:
        """Retorna o aplicativo atualmente selecionado."""
        selected = self.tree_apps.selectedItems()
        if selected:
            return selected[0].data(0, Qt.ItemDataRole.UserRole)
        return None

    def accept_open(self):
        """Executa a abertura e aplica a definição de padrão caso o checkbox esteja marcado."""
        app = self.get_selected_app()
        if not app:
            return

        set_as_default = self.chk_default.isChecked()

        if set_as_default:
            if app.is_custom:
                QMessageBox.information(
                    self,
                    "Aplicativo Padrão",
                    "Executáveis personalizados sem arquivo .desktop não podem ser registrados globalmente como padrão do sistema.",
                )
            else:
                success = MimeManager.set_default_app_for_mime(app.desktop_id, self.mime_type)
                if not success:
                    QMessageBox.warning(
                        self,
                        "Aviso",
                        f"Não foi possível salvar {app.name} como padrão global do sistema para {self.mime_type}.",
                    )

        # Executa o aplicativo com os arquivos selecionados
        launched = MimeManager.launch_app(app, self.filepaths)
        if not launched:
            QMessageBox.critical(
                self,
                "Erro ao Abrir",
                f"Falha ao iniciar o aplicativo '{app.name}'. Verifique se o executável existe e está acessível.",
            )
            return

        self.accept()
