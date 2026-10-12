import os
import sys
import shutil
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.main_window import QDirMainWindow

class TestPanelMaximizeAndScroll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_scroll_test_")
        for i in range(50):
            os.makedirs(os.path.join(self.test_dir, f"dir_{i:02d}"))
        self.sub_dir = os.path.join(self.test_dir, "dir_25")
        for i in range(50):
            os.makedirs(os.path.join(self.sub_dir, f"sub_{i:02d}"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scroll_resets_to_top_on_navigation(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(1000, 500)
        pane.show()
        pane.navigate_to(self.test_dir)

        for _ in range(25):
            self.app.processEvents()
            time.sleep(0.01)

        # Rola para baixo
        pane.table_view.verticalScrollBar().setValue(20)
        self.app.processEvents()
        self.assertGreater(pane.table_view.verticalScrollBar().value(), 0)

        # Navega para a subpasta
        pane.navigate_to(self.sub_dir)

        for _ in range(25):
            self.app.processEvents()
            time.sleep(0.01)

        # O scrollbar vertical DEVE estar zerado (topo)
        self.assertEqual(pane.table_view.verticalScrollBar().value(), 0)
        # E o item selecionado/ativo deve ser a linha 0
        proxy_idx = pane.table_view.rootIndex()
        if pane.proxy_model.rowCount(proxy_idx) > 0:
            self.assertEqual(pane.table_view.currentIndex().row(), 0)

        pane.deleteLater()

    def test_maximize_and_restore_active_pane(self):
        win = QDirMainWindow()
        # Garante layout 0 (4 painéis)
        win.switch_layout(0)
        self.app.processEvents()

        self.assertFalse(win.layout_manager.is_pane_maximized())
        self.assertTrue(win.panes[0].isHidden() == False)
        self.assertTrue(win.panes[1].isHidden() == False)
        self.assertTrue(win.panes[2].isHidden() == False)
        self.assertTrue(win.panes[3].isHidden() == False)

        # Maximiza painel ativo (painel 0)
        win.toggle_maximize_active_pane()
        self.app.processEvents()
        self.assertTrue(win.layout_manager.is_pane_maximized())
        self.assertTrue(win.panes[0].isHidden() == False)
        self.assertFalse(win.panes[1].isHidden() == False)
        self.assertFalse(win.panes[2].isHidden() == False)
        self.assertFalse(win.panes[3].isHidden() == False)
        self.assertTrue(win.btn_maximize.isChecked())

        # Restaura layout
        win.toggle_maximize_active_pane()
        self.app.processEvents()
        self.assertFalse(win.layout_manager.is_pane_maximized())
        self.assertTrue(win.panes[0].isHidden() == False)
        self.assertTrue(win.panes[1].isHidden() == False)
        self.assertTrue(win.panes[2].isHidden() == False)
        self.assertTrue(win.panes[3].isHidden() == False)
        self.assertFalse(win.btn_maximize.isChecked())

        # Ativa painel 2 e maximiza ele
        win.on_pane_activated(win.panes[2])
        self.assertEqual(win.active_pane, win.panes[2])
        win.toggle_maximize_active_pane()
        self.app.processEvents()
        self.assertTrue(win.layout_manager.is_pane_maximized())
        self.assertFalse(win.panes[0].isHidden() == False)
        self.assertFalse(win.panes[1].isHidden() == False)
        self.assertTrue(win.panes[2].isHidden() == False)
        self.assertFalse(win.panes[3].isHidden() == False)

        # Restaura novamente
        win.toggle_maximize_active_pane()
        self.app.processEvents()
        self.assertFalse(win.layout_manager.is_pane_maximized())
        self.assertTrue(win.panes[0].isHidden() == False)
        self.assertTrue(win.panes[2].isHidden() == False)

        win.deleteLater()

if __name__ == "__main__":
    unittest.main()
