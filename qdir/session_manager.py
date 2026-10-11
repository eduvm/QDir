"""
SessionManager do QDir.
Gerencia persistência de estado do aplicativo em formato compatível com .qdr (Q-Dir) e JSON.
Salva: layout ativo (0-11), posições de splitters, pastas abertas em cada painel e abas.
"""

import json
import os
from typing import Dict, List, Optional
from urllib.parse import unquote


class SessionManager:
    """Carrega e salva sessões de trabalho do QDir."""

    @staticmethod
    def parse_qdr(filepath: str) -> dict:
        """Lê arquivo .qdr do Q-Dir original ou gerado por esta aplicação."""
        data = {
            "layout_id": 0,
            "tree_mode": 0,
            "splitters": [5000, 5000, 5000],
            "folders": [os.path.expanduser("~")] * 4,
            "tabs": [[os.path.expanduser("~")]] * 4,
        }

        raw_text = ""
        for enc in ["utf-16-le", "utf-8", "latin1"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    raw_text = f.read()
                break
            except Exception:
                continue

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()

            if key == "ViewMode":
                try:
                    data["layout_id"] = int(val)
                except ValueError:
                    pass
            elif key == "tree_mode":
                try:
                    data["tree_mode"] = int(val)
                except ValueError:
                    pass
            elif key == "SP0":
                try:
                    data["splitters"][0] = int(val)
                except Exception:
                    pass
            elif key == "SP1":
                try:
                    data["splitters"][1] = int(val)
                except Exception:
                    pass
            elif key == "SP2":
                try:
                    data["splitters"][2] = int(val)
                except Exception:
                    pass
            elif key.startswith("Folder"):
                # Folder1..Folder4
                try:
                    idx = int(key.replace("Folder", "")) - 1
                    if 0 <= idx < 4:
                        # Extrai caminho se for URL encoded ou texto puro
                        clean_val = unquote(val)
                        # Remove flags adicionais se houver (ex: &ViewModeFlags2=...)
                        if "&" in clean_val:
                            clean_val = clean_val.split("&")[0]
                        # Converte barras Windows se necessário
                        if os.path.isdir(clean_val):
                            data["folders"][idx] = clean_val
                        else:
                            # Se for caminho Windows, usa HOME
                            data["folders"][idx] = os.path.expanduser("~")
                except Exception:
                    pass

        return data

    @staticmethod
    def save_qdr(filepath: str, session_data: dict):
        """Salva a sessão em formato .qdr do Q-Dir."""
        lines = [
            "\ufeffQ-Dir Version=8.04",
            f"ViewMode={session_data.get('layout_id', 0)}",
            f"tree_mode={session_data.get('tree_mode', 0)}",
            f"SP0={session_data.get('splitters', [5000, 5000, 5000])[0]}",
            f"SP1={session_data.get('splitters', [5000, 5000, 5000])[1]}",
            f"SP2={session_data.get('splitters', [5000, 5000, 5000])[2]}",
        ]
        folders = session_data.get("folders", [os.path.expanduser("~")] * 4)
        for i in range(4):
            path = folders[i] if i < len(folders) else os.path.expanduser("~")
            lines.append(f"Folder{i+1}={path}")

        # Salva em UTF-16LE para compatibilidade máxima com Windows Q-Dir
        with open(filepath, "w", encoding="utf-16-le") as f:
            f.write("\r\n".join(lines) + "\r\n")

    @staticmethod
    def save_json(filepath: str, session_data: dict):
        """Salva a sessão em formato JSON moderno com abas detalhadas."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_json(filepath: str) -> dict:
        """Carrega sessão em formato JSON."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
