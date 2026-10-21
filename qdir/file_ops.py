"""
Módulo de operações de arquivo para o QDir Linux.
Inclui cópia, movimentação, exclusão (lixeira/permanente), abertura em terminal,
cálculo assíncrono de tamanho de pasta e Renomeação em Lote (Batch Rename).
"""

import errno
import os
import shutil
import subprocess
import time
from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
import send2trash


def open_file_default(filepath: str):
    """Abre arquivo com aplicativo padrão do sistema Linux."""
    from qdir.mime_manager import MimeManager
    if not MimeManager.launch_default(filepath):
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
    size_bytes = max(0, int(size_bytes))
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


def format_time_remaining(seconds: float) -> str:
    """Formata tempo restante estimado em formato legível."""
    seconds = max(0.0, float(seconds))
    if seconds <= 0:
        return "Concluindo..."
    elif seconds < 60:
        return f"aprox. {max(1, int(round(seconds)))} s"
    elif seconds < 3600:
        m = int(seconds // 60)
        s = int(round(seconds % 60))
        if s == 60:
            m += 1
            s = 0
        return f"aprox. {m} min {s} s"
    else:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"aprox. {h} h {m} min"



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


class OperationCancelled(Exception):
    """Exceção levantada quando o usuário cancela a transferência."""
    pass


class FileTransferWorker(QThread):
    """Worker assíncrono para transferência de arquivos em blocos com relatório de progresso e cancelamento seguro."""
    progress_updated = pyqtSignal(object, object, str, float, float)  # bytes_done (qint64/pyint), total_bytes, current_item, speed_bps, eta_seconds
    item_started = pyqtSignal(str, int, int)                          # item_name, current_idx, total_items
    operation_finished = pyqtSignal(int, list, bool)                  # success_count, errors, was_cancelled

    def __init__(self, planned_items: List[Tuple[str, str]], is_move: bool = False, parent=None):
        super().__init__(parent)
        self.planned_items = planned_items
        self.is_move = is_move
        self._is_cancelled = False
        self._bytes_copied = 0
        self.total_bytes = 0
        self.success_count = 0
        self.errors: List[str] = []
        self._start_time = 0.0
        self._last_emit_time = 0.0
        self._last_speed_time = 0.0
        self._last_speed_bytes = 0
        self._current_speed = 0.0

    def cancel(self):
        self._is_cancelled = True

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _get_item_size(self, path: str) -> int:
        if os.path.islink(path):
            return 0
        if os.path.isfile(path):
            try:
                return os.path.getsize(path)
            except OSError:
                return 0
        if os.path.isdir(path):
            size = 0
            for root, _, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        try:
                            size += os.path.getsize(fp)
                        except OSError:
                            pass
            return size
        return 0

    def _calculate_total_bytes(self) -> int:
        total = 0
        for src, _ in self.planned_items:
            total += self._get_item_size(src)
        return total

    def _emit_progress(self, item_name: str, force: bool = False):
        now = time.time()
        if force or (now - self._last_emit_time >= 0.08) or (self.total_bytes > 0 and self._bytes_copied >= self.total_bytes):
            elapsed = max(0.001, now - self._start_time)
            dt = max(0.001, now - self._last_speed_time)
            if dt >= 0.2:
                inst_speed = max(0.0, (self._bytes_copied - self._last_speed_bytes) / dt)
                if self._current_speed == 0.0:
                    self._current_speed = inst_speed
                else:
                    self._current_speed = 0.7 * self._current_speed + 0.3 * inst_speed
                self._last_speed_time = now
                self._last_speed_bytes = self._bytes_copied

            speed = self._current_speed if self._current_speed > 0 else (self._bytes_copied / elapsed)
            rem = max(0, self.total_bytes - self._bytes_copied)
            eta = (rem / speed) if (speed > 0 and rem > 0) else 0.0
            self.progress_updated.emit(self._bytes_copied, self.total_bytes, item_name, speed, eta)
            self._last_emit_time = now

    def _copy_file(self, src_file: str, dst_file: str):
        if self._is_cancelled:
            raise OperationCancelled()

        # Remove arquivo ou link existente no destino se houver
        if os.path.exists(dst_file) or os.path.islink(dst_file):
            try:
                if os.path.isdir(dst_file) and not os.path.islink(dst_file):
                    shutil.rmtree(dst_file)
                else:
                    os.remove(dst_file)
            except OSError:
                pass

        os.makedirs(os.path.dirname(os.path.abspath(dst_file)), exist_ok=True)
        chunk_size = 1024 * 1024  # 1 MB

        try:
            with open(src_file, "rb") as fsrc, open(dst_file, "wb") as fdst:
                while True:
                    if self._is_cancelled:
                        raise OperationCancelled()
                    buf = fsrc.read(chunk_size)
                    if not buf:
                        break
                    fdst.write(buf)
                    self._bytes_copied += len(buf)
                    self._emit_progress(os.path.basename(src_file))

            shutil.copystat(src_file, dst_file)
            self._emit_progress(os.path.basename(src_file), force=True)
        except OperationCancelled:
            if os.path.exists(dst_file):
                try:
                    os.remove(dst_file)
                except OSError:
                    pass
            raise
        except Exception:
            if os.path.exists(dst_file):
                try:
                    os.remove(dst_file)
                except OSError:
                    pass
            raise

    def _copy_dir(self, src_dir: str, dst_dir: str):
        os.makedirs(dst_dir, exist_ok=True)
        for root, dirs, files in os.walk(src_dir):
            if self._is_cancelled:
                raise OperationCancelled()
            rel_path = os.path.relpath(root, src_dir)
            target_root = os.path.join(dst_dir, rel_path) if rel_path != "." else dst_dir
            for d in dirs:
                os.makedirs(os.path.join(target_root, d), exist_ok=True)
            for f in files:
                if self._is_cancelled:
                    raise OperationCancelled()
                sf = os.path.join(root, f)
                df = os.path.join(target_root, f)
                if os.path.islink(sf):
                    link_target = os.readlink(sf)
                    if os.path.exists(df) or os.path.islink(df):
                        os.remove(df)
                    os.symlink(link_target, df)
                else:
                    self._copy_file(sf, df)
        shutil.copystat(src_dir, dst_dir)

    def run(self):
        self.total_bytes = self._calculate_total_bytes()
        self._start_time = time.time()
        self._last_emit_time = self._start_time
        self._last_speed_time = self._start_time
        self._last_speed_bytes = 0
        self._current_speed = 0.0
        total_items = len(self.planned_items)

        for idx, (src, target) in enumerate(self.planned_items):
            if self._is_cancelled:
                break

            base_name = os.path.basename(src)
            self.item_started.emit(base_name, idx + 1, total_items)

            try:
                # Otimização de movimentação na mesma partição/filesystem (instantâneo)
                if self.is_move:
                    try:
                        src_size = self._get_item_size(src)
                        if os.path.exists(target) or os.path.islink(target):
                            if os.path.isdir(target) and not os.path.islink(target):
                                shutil.rmtree(target)
                            else:
                                os.remove(target)
                        os.rename(src, target)
                        self._bytes_copied += src_size
                        self._emit_progress(base_name, force=True)
                        self.success_count += 1
                        continue
                    except OSError as e:
                        if e.errno != errno.EXDEV:
                            raise
                        # EXDEV: partição diferente, faz cópia + remoção

                if os.path.isdir(src) and not os.path.islink(src):
                    self._copy_dir(src, target)
                    if self.is_move and not self._is_cancelled:
                        shutil.rmtree(src)
                else:
                    self._copy_file(src, target)
                    if self.is_move and not self._is_cancelled:
                        os.remove(src)

                self.success_count += 1

            except OperationCancelled:
                break
            except Exception as e:
                self.errors.append(f"{base_name}: {str(e)}")

        self.operation_finished.emit(self.success_count, self.errors, self._is_cancelled)


class FileTransferProgressDialog(QDialog):
    """Diálogo com barra de progresso, velocidade, tempo estimado e cancelamento para cópia/movimentação."""
    cancel_requested = pyqtSignal()

    def __init__(self, worker: FileTransferWorker, is_move: bool = False, parent=None):
        super().__init__(parent)
        self.worker = worker
        self.is_move = is_move
        self._started = False

        action_title = "Movendo arquivos..." if is_move else "Copiando arquivos..."
        self.setWindowTitle(action_title)
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        self.lbl_item = QLabel("Preparando transferência...")
        self.lbl_item.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.lbl_item)

        self.lbl_substatus = QLabel("")
        self.lbl_substatus.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.lbl_substatus)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #aaa;
                border-radius: 4px;
                text-align: center;
                height: 24px;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #2b78e4;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.lbl_speed_eta = QLabel("")
        self.lbl_speed_eta.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_speed_eta)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        # Conexões com o worker
        self.worker.item_started.connect(self.update_item_started)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.operation_finished.connect(self._on_worker_finished)
        self.cancel_requested.connect(self.worker.cancel)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._started:
            self._started = True
            if not self.worker.isRunning() and not self.worker.isFinished():
                self.worker.start()

    def _on_cancel_clicked(self):
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Cancelando...")
        self.lbl_item.setText("Cancelando transferência...")
        self.lbl_speed_eta.setText("Aguarde a finalização dos arquivos em andamento...")
        self.cancel_requested.emit()

    def closeEvent(self, event):
        if self.btn_cancel.isEnabled() and not self.worker.isFinished():
            self._on_cancel_clicked()
            event.ignore()
        else:
            event.accept()

    def _on_worker_finished(self, success_count: int, errors: list, was_cancelled: bool):
        self.accept()

    def update_item_started(self, item_name: str, current_idx: int, total_items: int):
        action = "Movendo" if self.is_move else "Copiando"
        self.lbl_item.setText(f"{action}: {item_name}")
        if total_items > 1:
            self.lbl_substatus.setText(f"Item {current_idx} de {total_items}")
        else:
            self.lbl_substatus.setText("")

    def update_progress(self, bytes_done: int, total_bytes: int, item_name: str, speed: float, eta: float):
        if total_bytes > 0:
            percent = min(100, int((bytes_done / total_bytes) * 100))
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent}% ({format_size(bytes_done)} de {format_size(total_bytes)})")
        else:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("100%")

        speed_str = f"{format_size(int(speed))}/s" if speed > 0 else "--"
        eta_str = format_time_remaining(eta) if (eta > 0 and bytes_done < total_bytes) else "--"
        self.lbl_speed_eta.setText(f"Velocidade: {speed_str}   |   Tempo restante: {eta_str}")


def copy_or_move_items(
    src_paths: List[str],
    dst_dir: str,
    is_move: bool = False,
    parent=None,
    show_progress: bool = True,
) -> Tuple[int, List[str]]:
    """Copia ou move múltiplos itens para o diretório de destino com diálogo de conflito e barra de progresso."""
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

    planned_items: List[Tuple[str, str]] = []

    for src in clean_srcs:
        base_name = os.path.basename(src)
        target = os.path.join(dst_dir, base_name)

        # Caso 1: Cópia no mesmo diretório (cria cópia automática sem perguntar)
        if os.path.abspath(src) == os.path.abspath(target):
            if is_move:
                continue
            name, ext = os.path.splitext(base_name)
            counter = 1
            target = os.path.join(dst_dir, f"{name} (cópia {counter}){ext}")
            while os.path.exists(target):
                counter += 1
                target = os.path.join(dst_dir, f"{name} (cópia {counter}){ext}")
            planned_items.append((src, target))
            continue

        # Caso 2: Conflito com item existente vindo de outra pasta
        if os.path.exists(target):
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
                return 0, []
            elif action == FileConflictDialog.SKIP:
                continue
            elif action == FileConflictDialog.KEEP_BOTH:
                name, ext = os.path.splitext(base_name)
                counter = 1
                target = os.path.join(dst_dir, f"{name} ({counter}){ext}")
                while os.path.exists(target):
                    counter += 1
                    target = os.path.join(dst_dir, f"{name} ({counter}){ext}")
                planned_items.append((src, target))
            elif action == FileConflictDialog.OVERWRITE:
                planned_items.append((src, target))
            else:
                return 0, []
        else:
            planned_items.append((src, target))

    if not planned_items:
        return 0, []

    app = QApplication.instance()
    is_offscreen = (app and app.platformName() == "offscreen")

    # Localiza janela principal que possui suporte a progresso na barra de status
    main_win = parent
    while main_win is not None and not hasattr(main_win, "start_transfer_progress"):
        if hasattr(main_win, "window") and callable(main_win.window):
            candidate = main_win.window()
            if candidate is not None and candidate is not main_win:
                main_win = candidate
                continue
        if hasattr(main_win, "parent") and callable(main_win.parent):
            main_win = main_win.parent()
        else:
            main_win = None

    has_status_progress = (main_win is not None and hasattr(main_win, "start_transfer_progress"))

    worker = FileTransferWorker(planned_items, is_move=is_move, parent=parent)

    if show_progress and app is not None and not is_offscreen and has_status_progress:
        from PyQt6.QtCore import QEventLoop
        loop = QEventLoop()
        main_win.start_transfer_progress(worker, is_move=is_move)
        worker.operation_finished.connect(lambda cnt, errs, canc: loop.quit())
        worker.start()
        loop.exec()
        worker.wait()
        return worker.success_count, worker.errors
    else:
        worker.run()
        return worker.success_count, worker.errors


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


# =========================================================================
# Operações com Arquivos Compactados (Zip, Rar, 7z, Tar, etc.)
# =========================================================================

ARCHIVE_EXTENSIONS = (
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.bz2",
    ".tbz2",
    ".tar.xz",
    ".txz",
    ".gz",
    ".bz2",
    ".xz",
)


def is_archive_file(filepath: str) -> bool:
    """Verifica se o arquivo selecionado é um arquivo compactado suportado."""
    if not filepath or not os.path.isfile(filepath):
        return False
    lower = filepath.lower()
    return any(lower.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def get_archive_base_name(filepath: str) -> str:
    """Retorna o nome base do arquivo sem as extensões de compactação (ex: 'backup.tar.gz' -> 'backup')."""
    base = os.path.basename(filepath)
    lower = base.lower()
    for ext in (
        ".tar.gz", ".tar.bz2", ".tar.xz",
        ".tgz", ".tbz2", ".txz",
        ".zip", ".rar", ".7z", ".tar",
        ".gz", ".bz2", ".xz",
    ):
        if lower.endswith(ext):
            return base[:-len(ext)]
    name, _ = os.path.splitext(base)
    return name


def extract_archive(archive_path: str, dest_dir: str) -> Tuple[bool, str]:
    """
    Extrai o arquivo compactado para dest_dir.
    Suporta .zip, .rar, .7z, .tar, .tar.gz, .tgz, .tar.bz2, .tbz2, .tar.xz, .txz, .gz, .bz2, .xz.
    """
    if not os.path.isfile(archive_path):
        return False, f"Arquivo compactado não encontrado: {archive_path}"

    try:
        os.makedirs(dest_dir, exist_ok=True)
    except Exception as e:
        return False, f"Falha ao criar diretório de destino: {str(e)}"

    lower = archive_path.lower()
    has_7z = bool(shutil.which("7z"))

    # 1. Arquivos RAR ou 7Z usando utilitário de sistema
    if lower.endswith(".rar") or lower.endswith(".7z"):
        if has_7z:
            cmd = ["7z", "x", "-y", f"-o{dest_dir}", archive_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return True, ""
            err_msg = res.stderr.strip() or res.stdout.strip()
            return False, f"Falha ao extrair com 7z (código {res.returncode}): {err_msg}"
        if lower.endswith(".rar") and shutil.which("unrar"):
            cmd = ["unrar", "x", "-o+", "-y", archive_path, f"{dest_dir}/"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode in (0, 1):
                return True, ""
            return False, f"Falha ao extrair com unrar: {res.stderr.strip()}"
        return False, "Para extrair arquivos deste formato, instale o pacote p7zip (7z) ou unrar no sistema."

    # 2. Formato ZIP (Python nativo zipfile com fallback)
    if lower.endswith(".zip"):
        try:
            import zipfile
            with zipfile.ZipFile(archive_path, "r") as zf:
                dest_resolved = os.path.realpath(dest_dir)
                for member in zf.infolist():
                    target_path = os.path.realpath(os.path.join(dest_dir, member.filename))
                    if not target_path.startswith(dest_resolved + os.sep) and target_path != dest_resolved:
                        continue
                    zf.extract(member, dest_dir)
            return True, ""
        except Exception as e:
            if has_7z:
                res = subprocess.run(["7z", "x", "-y", f"-o{dest_dir}", archive_path], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, ""
            if shutil.which("unzip"):
                res = subprocess.run(["unzip", "-o", "-q", archive_path, "-d", dest_dir], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, ""
            return False, f"Erro ao extrair zip: {str(e)}"

    # 3. Formato TAR (*.tar, *.tar.gz, *.tgz, *.tar.bz2, *.tbz2, *.tar.xz, *.txz)
    if any(lower.endswith(ext) for ext in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")):
        try:
            import tarfile
            with tarfile.open(archive_path, "r:*") as tf:
                if hasattr(tarfile, "data_filter"):
                    tf.extractall(dest_dir, filter="data")
                else:
                    dest_resolved = os.path.realpath(dest_dir)
                    for member in tf.getmembers():
                        target_path = os.path.realpath(os.path.join(dest_dir, member.name))
                        if not target_path.startswith(dest_resolved + os.sep) and target_path != dest_resolved:
                            continue
                        tf.extract(member, dest_dir)
            return True, ""
        except Exception as e:
            if has_7z:
                res = subprocess.run(["7z", "x", "-y", f"-o{dest_dir}", archive_path], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, ""
            if shutil.which("tar"):
                res = subprocess.run(["tar", "-xf", archive_path, "-C", dest_dir], capture_output=True, text=True)
                if res.returncode == 0:
                    return True, ""
            return False, f"Erro ao extrair tar: {str(e)}"

    # 4. Arquivos comprimidos simples (.gz, .bz2, .xz)
    if any(lower.endswith(ext) for ext in (".gz", ".bz2", ".xz")):
        base_out = get_archive_base_name(archive_path)
        target_out = os.path.join(dest_dir, base_out)
        try:
            if lower.endswith(".gz"):
                import gzip
                with gzip.open(archive_path, "rb") as f_in, open(target_out, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                return True, ""
            elif lower.endswith(".bz2"):
                import bz2
                with bz2.open(archive_path, "rb") as f_in, open(target_out, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                return True, ""
            elif lower.endswith(".xz"):
                import lzma
                with lzma.open(archive_path, "rb") as f_in, open(target_out, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                return True, ""
        except Exception as e:
            return False, f"Erro ao descompactar: {str(e)}"

    # 5. Fallback via shutil.unpack_archive
    try:
        shutil.unpack_archive(archive_path, dest_dir)
        return True, ""
    except Exception as e:
        return False, f"Falha na descompactação: {str(e)}"

