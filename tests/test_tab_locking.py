import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane
from qdir.main_window import QDirMainWindow

class TestTabLocking(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qdir_test_")
        self.sub1 = os.path.join(self.test_dir, "sub1")
        self.sub2 = os.path.join(self.sub1, "sub2")
        os.makedirs(self.sub2, exist_ok=True)
        self.color_engine = ColorEngine()
        self.pane = QDirPane(pane_id=1, color_engine=self.color_engine)
        self.pane.navigate_to(self.test_dir)

    def tearDown(self):
        self.pane.deleteLater()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initial_state(self):
        self.assertEqual(self.pane.tabs.count(), 1)
        self.assertFalse(self.pane.is_tab_locked(0))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(self.pane.tabs.tabText(0), base_name)

    def test_tab_lock_and_subdirectories_navigation(self):
        # 1. Bloquear aba na pasta raiz
        self.pane.set_tab_locked(0, True)
        self.assertTrue(self.pane.is_tab_locked(0))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 2. Navegar para subdiretório permitido
        self.pane.navigate_to(self.sub1)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub1))
        # Título da aba DEVE continuar sendo o nome fixo da raiz
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 3. Navegar para sub-subdiretório permitido
        self.pane.navigate_to(self.sub2)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub2))
        self.assertEqual(self.pane.tabs.tabText(0), f"🔒 {base_name}")

        # 4. Subir (go_up) até a raiz
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.sub1))
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

        # 5. Tentar subir ALÉM da raiz (deve ignorar)
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

        # 6. Tentar navegar diretamente para fora da raiz (deve ignorar)
        parent_dir = os.path.dirname(self.test_dir)
        self.pane.navigate_to(parent_dir)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))
        self.pane.navigate_to("/tmp")
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.test_dir))

    def test_locked_tab_cannot_be_closed(self):
        # Adicionar segunda aba para permitir fechamento
        self.pane.add_tab(self.sub1)
        self.assertEqual(self.pane.tabs.count(), 2)

        # Bloquear a aba 0
        self.pane.set_tab_locked(0, True)
        self.assertTrue(self.pane.is_tab_locked(0))

        # Tentar fechar a aba 0
        self.pane.on_tab_close(0)
        # Deve ser ignorado, contagem permanece 2
        self.assertEqual(self.pane.tabs.count(), 2)

        # Desbloquear aba 0 e tentar fechar novamente
        self.pane.set_tab_locked(0, False)
        self.assertFalse(self.pane.is_tab_locked(0))
        self.pane.on_tab_close(0)
        self.assertEqual(self.pane.tabs.count(), 1)

    def test_persistence_of_locked_tabs(self):
        win = QDirMainWindow()
        test_cfg = os.path.join(self.test_dir, "test_settings.json")
        win.get_settings_path = lambda: test_cfg

        p0 = win.panes[0]
        p0.set_tab_locked(0, False)
        while p0.tabs.count() > 1:
            p0.tabs.removeTab(p0.tabs.count() - 1)
        p0.navigate_to(self.test_dir)
        p0.set_tab_locked(0, True)
        p0.navigate_to(self.sub1)

        win.save_settings()
        self.assertTrue(os.path.exists(test_cfg))

        win2 = QDirMainWindow()
        win2.get_settings_path = lambda: test_cfg
        win2.load_settings()

        p0_restored = win2.panes[0]
        self.assertTrue(p0_restored.is_tab_locked(0))
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.sub1))
        base_name = os.path.basename(self.test_dir)
        self.assertEqual(p0_restored.tabs.tabText(0), f"🔒 {base_name}")

        p0_restored.go_up()
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.test_dir))
        p0_restored.go_up()
        self.assertEqual(os.path.realpath(p0_restored.current_path), os.path.realpath(self.test_dir))

        win.deleteLater()
        win2.deleteLater()

if __name__ == "__main__":
    unittest.main()
