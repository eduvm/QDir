import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from qdir.color_engine import ColorEngine
from qdir.pane import QDirPane, is_accessible_dir, find_accessible_ancestor


class TestAccessibleParentNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self.root_temp = tempfile.mkdtemp(prefix="qdir_parent_test_")
        self.color_engine = ColorEngine()
        self.pane = QDirPane(pane_id=1, color_engine=self.color_engine)

    def tearDown(self):
        self.pane.deleteLater()
        shutil.rmtree(self.root_temp, ignore_errors=True)

    def test_find_accessible_ancestor_normal(self):
        """No cenário normal onde a pasta pai existe, deve retornar a pasta pai imediata."""
        p1 = os.path.join(self.root_temp, "p1")
        os.makedirs(p1, exist_ok=True)
        ancestor = find_accessible_ancestor(p1)
        self.assertEqual(os.path.realpath(ancestor), os.path.realpath(self.root_temp))

    def test_find_accessible_ancestor_when_intermediate_deleted(self):
        """
        Cenário do usuário:
        projetos/ -> projeto 3/ -> 3/
        Remove 'projeto 3/'. Ao procurar ancestral de 'projeto 3/3', deve encontrar 'projetos/'.
        """
        projetos = os.path.join(self.root_temp, "projetos")
        projeto3 = os.path.join(projetos, "projeto 3")
        pasta3 = os.path.join(projeto3, "3")
        os.makedirs(pasta3, exist_ok=True)

        # QDir entra em 'pasta3'
        self.pane.navigate_to(pasta3)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(pasta3))

        # Outro programa exclui 'projeto 3' externamente
        shutil.rmtree(projeto3, ignore_errors=True)
        self.assertFalse(os.path.exists(projeto3))
        self.assertFalse(os.path.exists(pasta3))

        # A busca pelo pai acessível deve retornar 'projetos'
        ancestor = find_accessible_ancestor(self.pane.current_path)
        self.assertEqual(os.path.realpath(ancestor), os.path.realpath(projetos))

        # Ao chamar go_up (botão subir, atalho ou clique nos '..'), deve navegar para 'projetos'
        self.pane.go_up()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(projetos))

    def test_double_click_dot_dot_recovers_to_accessible_parent(self):
        """Simula o clique duplo no item '..' quando a pasta pai foi removida."""
        import time
        projetos = os.path.join(self.root_temp, "projetos")
        projeto3 = os.path.join(projetos, "projeto 3")
        pasta3 = os.path.join(projeto3, "3")
        os.makedirs(pasta3, exist_ok=True)

        self.pane.navigate_to(pasta3)

        # Aguarda carregamento inicial do QFileSystemModel
        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.01)

        # Deleta 'projeto 3' externamente
        shutil.rmtree(projeto3, ignore_errors=True)

        for _ in range(10):
            self.app.processEvents()
            time.sleep(0.01)

        # Simula o clique no item '..' (linha 0 do modelo que representa '..')
        proxy = self.pane.proxy_model
        dot_dot_index = proxy.index(0, 0, self.pane.table_view.rootIndex())
        self.pane.table_view.on_double_click(dot_dot_index)

        # Deve ter destravado e voltado para a pasta 'projetos' disponível
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(projetos))

    def test_refresh_recovers_when_current_dir_deleted(self):
        """Se a pasta atual foi removida, o comando refresh deve navegar para o primeiro pai acessível."""
        sub = os.path.join(self.root_temp, "a", "b", "c")
        os.makedirs(sub, exist_ok=True)
        self.pane.navigate_to(sub)

        # Remove 'a' externamente
        shutil.rmtree(os.path.join(self.root_temp, "a"), ignore_errors=True)

        self.pane.refresh()
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.root_temp))

    def test_locked_tab_deleted_root_unlocks_and_recovers(self):
        """Se a raiz de uma aba bloqueada for excluída externamente, deve desbloquear e subir."""
        locked_dir = os.path.join(self.root_temp, "locked")
        sub = os.path.join(locked_dir, "inside")
        os.makedirs(sub, exist_ok=True)

        self.pane.navigate_to(locked_dir)
        self.pane.set_tab_locked(0, True)
        self.assertTrue(self.pane.is_tab_locked(0))

        self.pane.navigate_to(sub)
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(sub))

        # Exclui a pasta locked inteira externamente
        shutil.rmtree(locked_dir, ignore_errors=True)

        # Sobe nível
        self.pane.go_up()

        # Deve ter desbloqueado a aba e voltado para self.root_temp
        self.assertFalse(self.pane.is_tab_locked(0))
        self.assertEqual(os.path.realpath(self.pane.current_path), os.path.realpath(self.root_temp))


if __name__ == "__main__":
    unittest.main()
