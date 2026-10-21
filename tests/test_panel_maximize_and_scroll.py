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

    def test_return_via_dot_dot_selects_and_scrolls_to_entered_subdirectory(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(600, 260)
        pane.show()
        pane.navigate_to(self.test_dir)

        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.01)

        deep_sub = os.path.join(self.test_dir, "dir_42")
        # Entra no subdiretório dir_42
        pane.navigate_to(deep_sub)
        for _ in range(25):
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(os.path.realpath(pane.current_path), os.path.realpath(deep_sub))

        # Simula duplo clique no item '..' (linha 0)
        root_idx = pane.table_view.rootIndex()
        dot_dot_idx = pane.proxy_model.index(0, 0, root_idx)
        pane.table_view.on_double_click(dot_dot_idx)

        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.01)

        # Deve ter retornado para self.test_dir
        self.assertEqual(os.path.realpath(pane.current_path), os.path.realpath(self.test_dir))

        # O subdiretório dir_42 deve estar selecionado como índice atual e na seleção
        curr_idx = pane.table_view.currentIndex()
        self.assertTrue(curr_idx.isValid())
        self.assertEqual(pane.proxy_model.data(curr_idx), "dir_42")
        selected_paths = [os.path.realpath(p) for p in pane.get_selected_paths()]
        self.assertEqual(selected_paths, [os.path.realpath(deep_sub)])

        # E deve estar visível na tela (rolado para baixo na tabela)
        self.assertGreater(pane.table_view.verticalScrollBar().value(), 0)
        vis_rect = pane.table_view.visualRect(curr_idx)
        self.assertTrue(pane.table_view.viewport().rect().intersects(vis_rect))

        pane.deleteLater()

    def test_go_up_from_cold_start_subdirectory_selects_and_scrolls(self):
        pane = QDirPane(1, ColorEngine())
        pane.resize(600, 260)
        pane.show()
        deep_sub = os.path.join(self.test_dir, "dir_45")
        # Inicia diretamente no subdiretório sem ter carregado o pai antes
        pane.navigate_to(deep_sub)
        for _ in range(25):
            self.app.processEvents()
            time.sleep(0.01)

        pane.go_up()
        for _ in range(35):
            self.app.processEvents()
            time.sleep(0.01)

        self.assertEqual(os.path.realpath(pane.current_path), os.path.realpath(self.test_dir))
        curr_idx = pane.table_view.currentIndex()
        self.assertTrue(curr_idx.isValid())
        self.assertEqual(pane.proxy_model.data(curr_idx), "dir_45")
        self.assertGreater(pane.table_view.verticalScrollBar().value(), 0)
        vis_rect = pane.table_view.visualRect(curr_idx)
        self.assertTrue(pane.table_view.viewport().rect().intersects(vis_rect))

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
