"""
ExportEngine do QDir.
Exporta listagem de arquivos da pasta ativa para formatos TXT, CSV e HTML com estilização.
Inspirado na funcionalidade de exportação e impressão do Q-Dir original (Menu 216).
"""

import csv
from datetime import datetime
import html
import os
from typing import List, Optional


def get_dir_items_data(dirpath: str) -> List[dict]:
    """Coleta informações de arquivos da pasta para exportação."""
    items = []
    try:
        entries = sorted(os.scandir(dirpath), key=lambda e: (not e.is_dir(), e.name.lower()))
        for entry in entries:
            try:
                stat = entry.stat()
                is_dir = entry.is_dir()
                size_str = "<PASTA>" if is_dir else f"{stat.st_size:,} bytes"
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                perms = oct(stat.st_mode)[-3:]
                items.append({
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size": size_str,
                    "raw_size": stat.st_size if not is_dir else 0,
                    "modified": mod_time,
                    "permissions": perms,
                })
            except Exception:
                continue
    except Exception:
        pass
    return items


def export_to_txt(dirpath: str, output_path: str):
    """Exporta a lista em formato de texto simples formatado."""
    items = get_dir_items_data(dirpath)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Listagem de Arquivos: {dirpath}\n")
        f.write(f"Gerado pelo QDir Linux em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n")
        f.write(f"{'Nome':<40} {'Tamanho':<16} {'Modificação':<20}\n")
        f.write("-" * 80 + "\n")
        for it in items:
            f.write(f"{it['name'][:38]:<40} {it['size']:<16} {it['modified']:<20}\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total de itens: {len(items)}\n")


def export_to_csv(dirpath: str, output_path: str):
    """Exporta a lista em formato CSV estruturado."""
    items = get_dir_items_data(dirpath)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Nome", "Tipo", "Tamanho (bytes)", "Última Modificação", "Permissões"])
        for it in items:
            t = "Pasta" if it["is_dir"] else "Arquivo"
            writer.writerow([it["name"], t, it["raw_size"], it["modified"], it["permissions"]])


def export_to_html(dirpath: str, output_path: str):
    """Exporta a lista em HTML estilizado similar ao modelo do Q-Dir original."""
    items = get_dir_items_data(dirpath)
    safe_dir = html.escape(dirpath)
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>QDir - {safe_dir}</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; color: #333; margin: 24px; }}
  h2 {{ color: #0066cc; margin-bottom: 4px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  th {{ background-color: #0066cc; color: white; text-align: left; padding: 10px 12px; font-size: 14px; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 13px; }}
  tr:nth-child(even) {{ background-color: #fcfcfc; }}
  tr:hover {{ background-color: #eef5ff; }}
  .dir {{ color: #008800; font-weight: bold; }}
  .file {{ color: #222; }}
  .size {{ text-align: right; }}
</style>
</head>
<body>
  <h2>Diretório: {safe_dir}</h2>
  <div class="meta">Exportado pelo QDir Linux em {now_str} &bull; Total: {len(items)} itens</div>
  <table>
    <thead>
      <tr>
        <th>Nome</th>
        <th style="width: 140px;" class="size">Tamanho</th>
        <th style="width: 180px;">Modificado</th>
        <th style="width: 100px;">Permissões</th>
      </tr>
    </thead>
    <tbody>
"""
    for it in items:
        css_class = "dir" if it["is_dir"] else "file"
        safe_name = html.escape(it["name"])
        html_content += f"""      <tr>
        <td class="{css_class}">{safe_name}</td>
        <td class="size">{it['size']}</td>
        <td>{it['modified']}</td>
        <td>{it['permissions']}</td>
      </tr>\n"""

    html_content += """    </tbody>
  </table>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
