import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication, QAbstractItemView

from qdir.color_engine import ColorEngine, RenameLineEdit
from qdir.pane import QDirPane


class TestRenameAndScroll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_test_rename_scroll_")
        for i in range(80):
            with open(os.path.join(self.test_dir, f"item_{i:02d}.txt"), "w") as f:
                f.write(f"content {i}")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_rename_enter_does_not_open_file_and_reselects(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(600, 300)
        pane.show()
        pane.navigate_to(self.test_dir)

        # Aguarda carregamento
        for _ in range(40):
            self.app.processEvents()
            time.sleep(0.01)

        table = pane.table_view
        rows = pane.proxy_model.rowCount(table.rootIndex())
        self.assertGreaterEqual(rows, 80)

        # Seleciona o item na linha 60 e rola para ele
        idx = pane.proxy_model.index(60, 0, table.rootIndex())
        table.setCurrentIndex(idx)
        table.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.app.processEvents()

        scroll_before = table.verticalScrollBar().value()
        self.assertGreater(scroll_before, 0)

        # Espiona abertura de arquivos
        opened_files = []
        pane.table_view.on_double_click = lambda index: opened_files.append(pane.fs_model.filePath(pane.proxy_model.mapToSource(index)))

        # Inicia renomeação inline
        table.rename_current_inline()
        self.app.processEvents()

        editor = table.viewport().findChild(RenameLineEdit)
        self.assertIsNotNone(editor)
        self.assertTrue(editor.isVisible())

        # Altera o nome e aperta Enter
        editor.setText("item_60_RENAMED.txt")
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(editor, ev)
        self.app.processEvents()

        # Aguarda sincronização do arquivo e do modelo
        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.01)

        # 1. Arquivo NÃO deve ter sido aberto!
        self.assertEqual(len(opened_files), 0, "O arquivo não deve ser aberto ao confirmar renomeação com Enter!")

        # 2. O scroll NÃO deve ter subido para o topo (valor 0)!
        scroll_after = table.verticalScrollBar().value()
        self.assertGreater(scroll_after, 0, "O scroll não deve resetar para o início (0) após renomear um arquivo!")

        # 3. O item renomeado deve estar selecionado
        curr = table.currentIndex()
        self.assertTrue(curr.isValid())
        self.assertEqual(pane.proxy_model.data(curr), "item_60_RENAMED.txt")

        pane.deleteLater()

    def test_directory_loaded_does_not_reset_scroll_when_already_in_directory(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(600, 300)
        pane.show()
        pane.navigate_to(self.test_dir)

        for _ in range(40):
            self.app.processEvents()
            time.sleep(0.01)

        table = pane.table_view
        idx = pane.proxy_model.index(50, 0, table.rootIndex())
        table.setCurrentIndex(idx)
        table.scrollTo(idx, QAbstractItemView.ScrollHint.PositionAtCenter)
        self.app.processEvents()

        scroll_val = table.verticalScrollBar().value()
        self.assertGreater(scroll_val, 0)

        # Simula sinal directoryLoaded subsequente (como o emitido por inotify ao criar ou alterar arquivos)
        pane._on_directory_loaded(self.test_dir)
        self.app.processEvents()

        self.assertEqual(table.verticalScrollBar().value(), scroll_val, "directoryLoaded não deve resetar o scroll se já estamos navegando no diretório!")

        pane.deleteLater()

    def test_rename_debounce_prevents_accidental_open(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(600, 300)
        pane.show()
        pane.navigate_to(self.test_dir)

        for _ in range(40):
            self.app.processEvents()
            time.sleep(0.01)

        table = pane.table_view
        opened_files = []
        table.on_double_click = lambda index: opened_files.append("opened")

        # Simula que uma renomeação acabou de ocorrer há 50ms
        table._last_rename_time = time.time() - 0.05

        # Pressiona Enter na tabela
        ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(table, ev)
        self.app.processEvents()

        self.assertEqual(len(opened_files), 0, "Enter dentro da janela de debounce pós-renomeação deve ser ignorado!")

        pane.deleteLater()


if __name__ == "__main__":
    unittest.main()
