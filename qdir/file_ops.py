"""
Módulo de operações de arquivo para o QDir Linux.
Inclui cópia, movimentação, exclusão (lixeira/permanente), abertura em terminal,
cálculo assíncrono de tamanho de pasta e Renomeação em Lote (Batch Rename).
"""

import os
import shutil
import subprocess
from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
import send2trash


def open_file_default(filepath: str):
    """Abre arquivo com aplicativo padrão do sistema Linux."""
    from PyQt6.QtCore import QUrl
    QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))


def open_in_terminal(dirpath: str):
    """Abre a pasta indicada no emulador de terminal disponível."""
    if not os.path.isdir(dirpath):
        dirpath = os.path.dirname(dirpath)

    terminals = [
        ["ptyxis", "--working-directory", dirpath],
        ["kgx", "--working-directory", dirpath],
        ["gnome-terminal", "--working-directory", dirpath],
        ["konsole", "--workdir", dirpath],
        ["alacritty", "--working-directory", dirpath],
        ["kitty", "--directory", dirpath],
        ["xfce4-terminal", "--working-directory", dirpath],
        ["x-terminal-emulator", "-e", f"sh -c 'cd \"{dirpath}\" && exec $SHELL'"],
        ["xterm", "-e", f"sh -c 'cd \"{dirpath}\" && exec $SHELL'"],
    ]

    for term_cmd in terminals:
        binary = term_cmd[0]
        if shutil.which(binary):
            try:
                subprocess.Popen(term_cmd)
                return True
            except Exception:
                continue
    return False


def trash_items(paths: List[str]) -> Tuple[int, List[str]]:
    """Envia arquivos ou pastas para a lixeira do sistema via send2trash."""
    success_count = 0
    errors = []
    clean_paths = [p for p in paths if os.path.basename(p) not in ("..", ".") and os.path.exists(p)]
    for p in clean_paths:
        try:
            send2trash.send2trash(p)
            success_count += 1
        except Exception as e:
            errors.append(f"{os.path.basename(p)}: {str(e)}")
    return success_count, errors


def delete_items_permanently(paths: List[str]) -> Tuple[int, List[str]]:
    """Remove permanentemente arquivos ou pastas."""
    success_count = 0
    errors = []
    clean_paths = [p for p in paths if os.path.basename(p) not in ("..", ".") and os.path.exists(p)]
    for p in clean_paths:
        try:
            if os.path.isdir(p) and not os.path.islink(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            success_count += 1
        except Exception as e:
            errors.append(f"{os.path.basename(p)}: {str(e)}")
    return success_count, errors


def format_size(size_bytes: int) -> str:
    """Formata tamanho de arquivo em formato legível (B, KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_mtime(timestamp: float) -> str:
    """Formata timestamp em data/hora legível."""
    import datetime
    dt = datetime.datetime.fromtimestamp(timestamp)
    return dt.strftime("%d/%m/%Y %H:%M:%S")


class FileConflictDialog(QDialog):
    """Diálogo de resolução de conflito quando o arquivo de destino já existe."""

    OVERWRITE = "overwrite"
    KEEP_BOTH = "keep_both"
    SKIP = "skip"
    CANCEL = "cancel"

    def __init__(
        self,
        src_path: str,
        dst_path: str,
        is_move: bool = False,
        has_multiple: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.src_path = src_path
        self.dst_path = dst_path
        self.is_move = is_move
        self.result_action = self.CANCEL
        self.apply_to_all = False

        action_name = "mover" if is_move else "copiar"
        self.setWindowTitle("Substituir Arquivo Existente" if not is_move else "Substituir ao Mover")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        base_name = os.path.basename(dst_path)
        is_dir = os.path.isdir(dst_path)
        item_type = "uma pasta" if is_dir else "um arquivo"

        # Mensagem Principal com ícone
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_icon = QLabel()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        lbl_icon.setPixmap(icon.pixmap(48, 48))
        header_layout.addWidget(lbl_icon)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        lbl_title = QLabel(f"<b>Já existe {item_type} com o nome \"{base_name}\" nesta pasta.</b>")
        lbl_title.setStyleSheet("font-size: 13px;")
        lbl_title.setWordWrap(True)
        text_layout.addWidget(lbl_title)

        lbl_sub = QLabel(f"Deseja substituir o item existente pelo novo que você está tentando {action_name}?")
        lbl_sub.setStyleSheet("color: palette(window-text);")
        lbl_sub.setWordWrap(True)
        text_layout.addWidget(lbl_sub)
        header_layout.addLayout(text_layout, stretch=1)

        layout.addLayout(header_layout)

        # Informações comparativas
        def get_info(path: str) -> Tuple[str, str]:
            if not os.path.exists(path):
                return "-", "-"
            try:
                st = os.stat(path)
                size_str = format_size(st.st_size) if not os.path.isdir(path) else "Pasta"
                time_str = format_mtime(st.st_mtime)
                return size_str, time_str
            except Exception:
                return "-", "-"

        dst_size, dst_time = get_info(dst_path)
        src_size, src_time = get_info(src_path)

        box_info = QFrame()
        box_info.setStyleSheet("""
            QFrame {
                background: palette(alternate-base);
                border: 1px solid rgba(128, 128, 128, 0.3);
                border-radius: 6px;
                padding: 6px;
            }
        """)
        info_layout = QVBoxLayout(box_info)
        info_layout.setSpacing(8)

        lbl_dst = QLabel(
            f"<b>Existente no destino:</b><br>"
            f"• Tamanho: {dst_size} &nbsp;&nbsp;|&nbsp;&nbsp; Modificado em: {dst_time}<br>"
            f"<span style='font-size: 11px; color: #888;'>{dst_path}</span>"
        )
        lbl_dst.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(lbl_dst)

        lbl_src = QLabel(
            f"<b>Novo a ser {'movido' if is_move else 'copiado'}:</b><br>"
            f"• Tamanho: {src_size} &nbsp;&nbsp;|&nbsp;&nbsp; Modificado em: {src_time}<br>"
            f"<span style='font-size: 11px; color: #888;'>{src_path}</span>"
        )
        lbl_src.setTextFormat(Qt.TextFormat.RichText)
        info_layout.addWidget(lbl_src)

        layout.addWidget(box_info)

        # Checkbox "Aplicar para todos" se houver múltiplos itens
        if has_multiple:
            self.chk_all = QCheckBox("Aplicar esta ação para todos os próximos conflitos")
            layout.addWidget(self.chk_all)
        else:
            self.chk_all = None

        # Botões de Ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        btn_overwrite = QPushButton("Substituir")
        btn_overwrite.setDefault(True)
        btn_overwrite.setStyleSheet("font-weight: bold;")
        btn_overwrite.clicked.connect(lambda: self._choose(self.OVERWRITE))
        btn_layout.addWidget(btn_overwrite)

        btn_keep = QPushButton("Manter Ambos")
        btn_keep.setToolTip("Gera uma cópia numerada (ex: arquivo (1).ext)")
        btn_keep.clicked.connect(lambda: self._choose(self.KEEP_BOTH))
        btn_layout.addWidget(btn_keep)

        btn_skip = QPushButton("Pular")
        btn_skip.setToolTip("Ignora a transferência deste item")
        btn_skip.clicked.connect(lambda: self._choose(self.SKIP))
        btn_layout.addWidget(btn_skip)

        btn_layout.addStretch(1)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(lambda: self._choose(self.CANCEL))
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

    def _choose(self, action: str):
        self.result_action = action
        if self.chk_all:
            self.apply_to_all = self.chk_all.isChecked()
        self.accept()


def copy_or_move_items(
    src_paths: List[str],
    dst_dir: str,
    is_move: bool = False,
    parent=None,
) -> Tuple[int, List[str]]:
    """Copia ou move múltiplos itens para o diretório de destino com diálogo de confirmação para conflitos."""
    if not os.path.isdir(dst_dir):
        return 0, ["Diretório de destino inválido."]

    clean_srcs = [p for p in src_paths if os.path.exists(p) and os.path.basename(p) not in ("..", ".")]
    if not clean_srcs:
        return 0, []

    # Detecta previamente itens em conflito (já existentes no destino)
    conflicts = [
        s for s in clean_srcs
        if os.path.exists(os.path.join(dst_dir, os.path.basename(s)))
        and os.path.abspath(s) != os.path.abspath(os.path.join(dst_dir, os.path.basename(s)))
    ]
    has_multiple_conflicts = len(conflicts) > 1
    apply_to_all_action = None

    success_count = 0
    errors = []

    for src in clean_srcs:
        try:
            base_name = os.path.basename(src)
            target = os.path.join(dst_dir, base_name)

            # Caso 1: Cópia no mesmo diretório (cria cópia automática sem perguntar)
            if os.path.abspath(src) == os.path.abspath(target):
                name, ext = os.path.splitext(base_name)
                counter = 1
                while os.path.exists(target):
                    target = os.path.join(dst_dir, f"{name} (cópia {counter}){ext}")
                    counter += 1

            # Caso 2: Conflito com item existente vindo de outra pasta
            elif os.path.exists(target):
                action = apply_to_all_action
                if not action:
                    dlg = FileConflictDialog(
                        src_path=src,
                        dst_path=target,
                        is_move=is_move,
                        has_multiple=has_multiple_conflicts,
                        parent=parent,
                    )
                    dlg.exec()
                    action = dlg.result_action
                    if dlg.apply_to_all:
                        apply_to_all_action = action

                if action == FileConflictDialog.CANCEL:
                    break
                elif action == FileConflictDialog.SKIP:
                    continue
                elif action == FileConflictDialog.KEEP_BOTH:
                    name, ext = os.path.splitext(base_name)
                    counter = 1
                    target = os.path.join(dst_dir, f"{name} ({counter}){ext}")
                    while os.path.exists(target):
                        counter += 1
                        target = os.path.join(dst_dir, f"{name} ({counter}){ext}")
                elif action == FileConflictDialog.OVERWRITE:
                    if os.path.isdir(target) and not os.path.islink(target):
                        shutil.rmtree(target)
                    else:
                        os.remove(target)
                else:
                    break

            if is_move:
                shutil.move(src, target)
            else:
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, target)
                else:
                    shutil.copy2(src, target)
            success_count += 1
        except Exception as e:
            errors.append(f"{os.path.basename(src)}: {str(e)}")

    return success_count, errors


class BatchRenameDialog(QDialog):
    """Diálogo de renomeação em lote inspirado no Dialog 313 do Q-Dir."""

    def __init__(self, filepaths: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renomeação em Lote - QDir")
        self.resize(700, 480)
        self.filepaths = sorted(filepaths)

        layout = QVBoxLayout(self)

        # Regras de renomeação
        form_layout = QVBoxLayout()

        # Localizar e substituir
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Localizar:"))
        self.txt_find = QLineEdit()
        row1.addWidget(self.txt_find)
        row1.addWidget(QLabel("Substituir por:"))
        self.txt_replace = QLineEdit()
        row1.addWidget(self.txt_replace)
        form_layout.addLayout(row1)

        # Prefixo / Sufixo / Numeração
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Prefixo:"))
        self.txt_prefix = QLineEdit()
        row2.addWidget(self.txt_prefix)
        row2.addWidget(QLabel("Sufixo:"))
        self.txt_suffix = QLineEdit()
        row2.addWidget(self.txt_suffix)
        form_layout.addLayout(row2)

        # Contador numérico
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Numeração inicial (use # para padrão numérico):"))
        self.txt_start_num = QLineEdit("1")
        self.txt_start_num.setFixedWidth(60)
        row3.addWidget(self.txt_start_num)
        row3.addStretch()

        btn_preview = QPushButton("Atualizar Pré-visualização")
        btn_preview.clicked.connect(self.update_preview)
        row3.addWidget(btn_preview)
        form_layout.addLayout(row3)

        layout.addLayout(form_layout)

        # Tabela de pré-visualização (Nome Atual vs Novo Nome)
        self.table = QTableWidget(len(self.filepaths), 2)
        self.table.setHorizontalHeaderLabels(["Nome Atual", "Novo Nome"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.txt_find.textChanged.connect(self.update_preview)
        self.txt_replace.textChanged.connect(self.update_preview)
        self.txt_prefix.textChanged.connect(self.update_preview)
        self.txt_suffix.textChanged.connect(self.update_preview)
        self.txt_start_num.textChanged.connect(self.update_preview)

        # Botões de ação
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.apply_rename)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.update_preview()

    def generate_new_name(self, old_name: str, index: int) -> str:
        base, ext = os.path.splitext(old_name)
        find_val = self.txt_find.text()
        replace_val = self.txt_replace.text()
        prefix = self.txt_prefix.text()
        suffix = self.txt_suffix.text()

        try:
            start_num = int(self.txt_start_num.text())
        except ValueError:
            start_num = 1
        num_str = f"{start_num + index:02d}"

        new_base = base
        if find_val:
            new_base = new_base.replace(find_val, replace_val)

        new_base = f"{prefix}{new_base}{suffix}"
        if "#" in new_base:
            new_base = new_base.replace("#", num_str)

        return f"{new_base}{ext}"

    def update_preview(self):
        for row, path in enumerate(self.filepaths):
            old_name = os.path.basename(path)
            new_name = self.generate_new_name(old_name, row)
            self.table.setItem(row, 0, QTableWidgetItem(old_name))
            self.table.setItem(row, 1, QTableWidgetItem(new_name))

    def apply_rename(self):
        renamed_count = 0
        errors = []
        for row, path in enumerate(self.filepaths):
            dir_path = os.path.dirname(path)
            old_name = os.path.basename(path)
            new_name = self.generate_new_name(old_name, row)
            if old_name != new_name:
                new_path = os.path.join(dir_path, new_name)
                try:
                    os.rename(path, new_path)
                    renamed_count += 1
                except Exception as e:
                    errors.append(f"{old_name} -> {new_name}: {str(e)}")

        if errors:
            QMessageBox.warning(self, "Erros na Renomeação", "\n".join(errors))
        self.accept()
