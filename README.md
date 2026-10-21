<p align="center">
  <img src="resources/qdir.png" alt="QDir Linux Logo" width="96" />
</p>

<h1 align="center">QDir Linux — Quad File Explorer</h1>

<p align="center">
  <strong>Gerenciador de arquivos multipainel nativo para Linux, escrito em Python 3.12 e PyQt6.</strong><br/>
  Inspirado na produtividade do clássico <em>Q-Dir (SoftwareOK)</em> e na ergonomia do <em>Double Commander</em>.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Platform-Linux-FCC624?logo=linux&logoColor=black" alt="Linux" />
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License MIT" />
</p>

---

## Visão Geral

O **QDir Linux** é um gerenciador de arquivos avançado de 4 painéis simultâneos desenvolvido nativamente para ambientes Linux (X11/Wayland). Ele combina a disposição multipainel do **Q-Dir** com recursos de navegação rápida, bloqueio de abas, renomeação cíclica e cursores dedicados de transferência inspirados no **Double Commander**.

---

## Principais Funcionalidades

### 1. 12 Modos de Layout & Maximização Instantânea
- **12 disposições multipainel dinâmicas:**
  1. `4-Quad (2x2 Padrão)`
  2. `3-Tri (2 Topo, 1 Embaixo)`
  3. `3-Tri (1 Topo, 2 Embaixo)`
  4. `3-Tri (1 Esquerda, 2 Direita)`
  5. `3-Tri (2 Esquerda, 1 Direita)`
  6. `4-Colunas Verticais`
  7. `4-Linhas Horizontais`
  8. `2-Dual Vertical (Lado a Lado)`
  9. `2-Dual Horizontal (Topo/Embaixo)`
  10. `1-Single (Painel Único)`
  11. `3-Colunas Verticais`
  12. `3-Linhas Horizontais`
- **Maximizar / Restaurar Painel Ativo:** alterne rapidamente entre o painel focado em tela cheia e o seu layout multipainel anterior usando `Ctrl+M`, `F11`, o botão **⛶ Maximizar** na barra de ferramentas ou dando duplo clique no indicador do painel (`#1`, `#2`, `#3`, `#4`).
- **3 Modos de Árvore de Diretórios:** Sem Árvore, 4 Árvores Individuais (uma por painel) ou 1 Árvore Compartilhada sincronizada à esquerda.

### 2. Abas Avançadas & Bloqueio de Raiz
- **Múltiplas abas por painel:** crie (`Ctrl+T`), duplique, reordene e feche abas (`Ctrl+W` ou clique com o botão do meio do mouse).
- **Alternância automática no Drag & Drop:** ao arrastar arquivos sobre outra aba e manter o cursor por `400 ms`, a aba é ativada automaticamente.
- **🔒 Bloqueio de Aba (Apenas Subdiretórios):**
  - Ao bloquear uma aba pelo menu de contexto, seu título é fixado na pasta-raiz (`🔒 NomeDaPasta`) e ela fica protegida contra fechamento acidental.
  - Permite navegar livremente em subdiretórios físicos e através de **links simbólicos (`symlinks`)** contidos dentro da árvore bloqueada (mesmo que apontem para outros discos/partições), bloqueando qualquer tentativa de subir além da raiz permitida.
  - Caso a pasta-raiz bloqueada seja removida externamente, a aba é desbloqueada automaticamente e recupera o primeiro ancestral acessível.

### 3. Navegação Inteligente e Resiliente
- **Memória de Subpasta ao Subir Nível (`..`):** ao entrar em um subdiretório e voltar para a pasta pai (clicando em `..`, pressionando `Backspace`, clicando em *Subir pasta* ou *Voltar*), o subdiretório de onde você saiu é automaticamente selecionado e rolado para ficar visível na tela.
- **Entrada `..` sempre fixa no topo:** mesmo ao ordenar por tamanho, extensão ou data (crescente ou decrescente), o item `..` permanece fixo na primeira linha e nunca é incluído no `Ctrl+A`.
- **Recuperação automática de pastas excluídas:** se o diretório atual ou pastas intermediárias forem excluídos por outro processo, os comandos de subir nível ou atualizar (`F5`) localizam automaticamente o primeiro diretório pai existente e acessível no disco.
- **Filtros em tempo real (Positivo e Negativo):** filtre arquivos instantaneamente na barra inferior de cada painel usando wildcards (ex.: filtro positivo `*.py;*.json` e filtro negativo `*.bak;*.tmp`), além de alternância rápida de arquivos ocultos (`Ctrl+H`).

### 4. Drag & Drop, Área de Transferência e Progresso Integrado
- **Semântica clara de arrasto com cursores estilo Double Commander:**
  - **Arrastar sem teclas modificadoras:** realiza **Cópia** (`+`).
  - **Arrastar segurando `Shift`:** realiza **Mover** (`→`), atualizando o cursor instantaneamente ao pressionar ou soltar a tecla durante o arrasto.
  - **Segurar `Ctrl` ao soltar:** exibe diálogo de confirmação antes de executar a transferência.
  - **Destaque visual de destino:** ao passar sobre uma subpasta durante o arrasto, a linha da pasta é destacada e a barra de status informa exatamente se a operação será *Copiar* ou *Mover* para aquela pasta.
- **Barra de Progresso na Barra de Status:** transferências de arquivos e diretórios rodam em segundo plano (`QThread`), exibindo progresso percentual, velocidade em tempo real (`MB/s`), tempo restante estimado (`ETA`) e botão de cancelamento seguro (que remove automaticamente qualquer arquivo parcial incompleto).
- **Resolução de Conflitos:** diálogo interativo ao encontrar arquivos existentes no destino com opções **Substituir**, **Ignorar** ou **Renomear (Manter Ambos)** (gerando sufixos `_1`, `_2`, etc.) e caixa *"Aplicar para todos os conflitos"*.
- **Clipboard compatível com FreeDesktop/GNOME:** suporte a `Ctrl+C`, `Ctrl+X` (com atenuação visual translúcida dos itens recortados) e `Ctrl+V` compatível com `x-special/gnome-copied-files` e `text/uri-list`.

### 5. Descompactação Integrada & Menu "Abrir com..."
- **Extração nativa de arquivos compactados:** suporte integrado no menu de contexto para `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tbz2`, `.tar.xz`, `.txz`, `.7z` e `.rar`, com opções:
  - *Extrair aqui*
  - *Extrair para `'nome_do_arquivo/'`* (ou cada arquivo em sua respectiva pasta quando múltiplos arquivos estão selecionados).
- **Menu "Abrir com" e Associação MIME:**
  - Lista automaticamente aplicativos compatíveis registrados no sistema FreeDesktop com seus respectivos ícones e indicação do aplicativo padrão atual.
  - Diálogo *"Escolher outro aplicativo..."* com busca em tempo real, comando customizado e opção **"Sempre usar este aplicativo para abrir este tipo de arquivo"** (sincronizado via `xdg-mime`, `gio mime` e `~/.config/mimeapps.list`).

### 6. Renomeação Inline Cíclica & Em Lote
- **Renomeação Inline (`F2`):**
  - Pressione `F2` repetidamente para alternar a seleção entre: **1º** apenas o nome base → **2º** apenas a extensão → **3º** o nome completo.
  - Use as setas `↑` / `↓` durante a edição inline para confirmar a renomeação atual e já abrir a edição do arquivo vizinho sem perder o foco nem resetar a rolagem.
- **Renomeação em Lote:** quando múltiplos itens estão selecionados, permite buscar/substituir texto e adicionar prefixos ou sufixos em massa.

### 7. Regras de Cores (Filter2) & Temas Adaptativos
- **Coloração por extensão e atributo (`Filter2`):** destaca visualmente diretórios (`#DIR`), ocultos (`#Hidden`), executáveis, vídeos, áudios, imagens, código-fonte e compactados. Inclui editor visual completo em *Ferramentas → Regras de Cores (Filter2)...* com persistência em `~/.config/qdir/color_rules.json` e leitura de arquivos `Q-Dir.ini`.
- **Integração com `qt6ct` e Temas Escuros:** carrega automaticamente esquemas de cores e fontes do `qt6ct` e renderiza ícones vetoriais de alto contraste adaptados à luminância do tema.
- **Tema Dinâmico do Wallpaper (Pywal / OpenRGB):** opção para monitorar `~/.cache/wal/colors.json` em tempo real e atualizar toda a interface automaticamente ao trocar o papel de parede.

---

## Atalhos de Teclado

| Atalho | Ação |
| :--- | :--- |
| `F2` | Iniciar renomeação inline (pressione novamente para alternar seleção nome / extensão / tudo) |
| `↑` / `↓` *(durante F2)* | Confirmar renomeação atual e editar o item anterior / seguinte |
| `Enter` / `Duplo Clique` | Abrir arquivo no aplicativo padrão, entrar na pasta ou subir nível em `..` |
| `Backspace` | Subir para a pasta pai (selecionando e exibindo a subpasta de onde saiu) |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copiar / Recortar / Colar arquivos e pastas |
| `Ctrl+A` | Selecionar todos os itens da pasta atual (excluindo automaticamente o `..`) |
| `Delete` | Mover itens selecionados para a Lixeira (`send2trash`) |
| `Shift+Delete` | Excluir itens selecionados permanentemente |
| `Ctrl+T` / `Ctrl+W` | Nova aba / Fechar aba ativa no painel focado |
| `Ctrl+H` | Exibir / Ocultar arquivos ocultos (`dotfiles`) |
| `Ctrl+M` ou `F11` | Maximizar / Restaurar o painel ativo |
| `Ctrl+Alt+T` | Abrir terminal na pasta do painel ativo |
| `F5` | Atualizar listagem de todos os painéis |
| **Arrastar (sem tecla)** | **Copiar** itens para o destino |
| **Arrastar + `Shift`** | **Mover** itens para o destino |
| **Arrastar + `Ctrl`** | Solicitar confirmação antes de concluir a cópia/movimentação |

---

## Instalação e Execução

### Pré-requisitos
- **Linux** (qualquer distribuição moderna com X11 ou Wayland)
- **Python 3.11+** (recomendado Python 3.12)
- Utilitários opcionais do sistema: `7z` (`p7zip-full`) ou `unrar` para extração de arquivos `.7z`/`.rar`.

### Opção 1: Usando Conda (Recomendado)
```bash
git clone https://github.com/eduvm/QDir.git
cd QDir
conda env create -f environment.yml
conda activate qdir
python3 qdir_app.py
```

### Opção 2: Usando `venv` + `pip`
```bash
git clone https://github.com/eduvm/QDir.git
cd QDir
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 qdir_app.py
```

---

## Estrutura do Projeto

```text
QDir/
├── qdir_app.py                  # Ponto de entrada, integração qt6ct e inicialização da GUI
├── environment.yml              # Definição do ambiente Conda (qdir)
├── requirements.txt             # Dependências Python (PyQt6, send2trash)
├── qdir/
│   ├── main_window.py           # Janela principal, menus, barra de ferramentas e barra de status
│   ├── pane.py                  # Painel de navegação (QDirPane), tabela (FileTableView), abas e filtros
│   ├── layout_manager.py        # Gerenciador dos 12 layouts multipainel, árvores e maximização
│   ├── file_ops.py              # Operações de arquivo assíncronas (QThread), conflitos, extração e lote
│   ├── color_engine.py          # Motor de regras de cores (Filter2), delegate visual e editor F2
│   ├── color_dialog.py          # Diálogo de gerenciamento de regras de cores
│   ├── clipboard_manager.py     # Gerenciador de área de transferência (Copiar/Recortar URI & GNOME)
│   ├── mime_manager.py          # Descoberta de aplicativos FreeDesktop (.desktop) e associações MIME
│   ├── open_with_dialog.py      # Diálogo "Abrir com..." e definição de aplicativo padrão
│   ├── session_manager.py       # Leitura/escrita de sessões (.json e legado .qdr)
│   ├── export_engine.py         # Exportação de listagens para HTML, CSV e TXT
│   ├── theme_manager.py         # Integração dinâmica com Pywal / OpenRGB (Wallpaper Theme)
│   └── ui_icons.py              # Renderizador de ícones vetoriais adaptativos e cursores de Drag & Drop
├── resources/                   # Ícone da aplicação e cursores de arrasto
└── tests/                       # Suíte de testes automatizados (unittest / offscreen Qt)
```

---

## Executando os Testes

A suíte de testes utiliza o modo `offscreen` do Qt (`QT_QPA_PLATFORM=offscreen`), podendo ser executada em qualquer terminal ou ambiente de CI sem necessidade de servidor gráfico ativo:

```bash
python3 -m unittest discover -s tests -v
```

---

## Configurações e Persistência Local

Os arquivos de configuração do usuário são salvos automaticamente seguindo o padrão XDG em `~/.config/qdir/`:
- `~/.config/qdir/settings.json`: layout ativo, dimensões da janela, estado dos divisores (`splitters`), larguras das colunas, diretórios abertos e abas bloqueadas de cada painel.
- `~/.config/qdir/color_rules.json`: regras personalizadas de cores por extensão/atributo.

---

## Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

> **Créditos:** Conceito visual multipainel inspirado no software original [Q-Dir (The Quad Explorer)](https://www.softwareok.com/?seite=Freeware/Q-Dir) criado por *Nenad Hrg (SoftwareOK.com)*, e mecânicas de produtividade inspiradas no [Double Commander](https://doublecmd.sourceforge.io/).
