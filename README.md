# QDir Linux (Quad Explorer)

Port nativo do clássico **Q-Dir** (SoftwareOK) para Linux, desenvolvido em **Python 3.12** e **PyQt6**.

Gerenciador de arquivos multilocular projetado para agilizar o fluxo de trabalho com até 4 painéis independentes, abas simultâneas, filtragem em tempo real, suporte total a temas do sistema e ampla compatibilidade.

---

## Principais Funcionalidades

- **12 Modos de Layout & Maximização do Painel Ativo:**
  - 4-Quad (2x2), 3-Tri (Topo/Embaixo, Esquerda/Direita), 4 Colunas/Linhas, 3 Colunas/Linhas, 2-Dual e 1-Single.
  - **Maximizar / Restaurar Painel Ativo:** atalho de teclado (`Ctrl+M` ou `F11`), botão na barra de ferramentas ou duplo clique no identificador do painel (`#1`, `#2`, `#3`, `#4`). Ao restaurar, retorna exatamente para a disposição multi-painel anterior.
- **Árvores de Diretórios:**
  - Sem árvore, 4 árvores individuais ou 1 árvore compartilhada na lateral esquerda.
- **Abas Independentes por Painel:**
  - Suporte a múltiplas abas, alternância automática ao passar o mouse com arrasto e fechamento com botão do meio.
  - **Bloqueio de Abas com Restrição a Subdiretórios (Estilo Double Commander):**
    - Clique com o botão direito na aba e selecione *"🔒 Bloquear Aba (Apenas Subdiretórios)"*.
    - O título fixa-se no nome da pasta-raiz (ex: `🔒 Downloads`) e não muda ao navegar.
    - Permite navegar livremente em subdiretórios descendentes, mas ignora comandos para subir além da raiz (`..`, `Backspace`, botão de subir, barra de endereços).
    - Proteção ativa contra fechamento acidental de abas bloqueadas.
    - Persistência automática do estado de bloqueio e pasta-raiz em `~/.config/qdir/settings.json`.
- **Drag & Drop e Área de Transferência (Estilo Double Commander):**
  - **Ação invertida ergonômica:** arrastar normal (sem teclas) realiza **Cópia** de arquivos; arrastar segurando **Control** realiza a operação de **Mover**.
  - **Feedback visual com cursores dedicados:** exibe cursores de arrasto idênticos aos do Double Commander (cursor com sinal `+` para Cópia e cursor com seta de movimento para Mover), alternando dinamicamente ao pressionar ou soltar `Ctrl`.
  - Arrastar e soltar arquivos entre painéis, sobre pastas filhas e sobre abas (com alternância automática de aba no hover).
  - Suporte completo a `Ctrl+C`, `Ctrl+X` (com atenuação visual translúcida de arquivos recortados) e `Ctrl+V` seguindo o padrão FreeDesktop / GNOME.
- **Navegação Inteligente & Abertura de Arquivos:**
  - Reset automático de scroll ao entrar em pastas: a visualização sempre abre no topo absoluto da lista (iniciando no `..`), sem retenção residual de rolagem de pastas anteriores.
  - Entrada fixa `..` no topo para retornar à pasta pai (via `Enter` ou duplo clique).
  - Duplo clique abre arquivos no aplicativo padrão ou navega em pastas.
  - `Backspace` para subir pasta.
- **Menu 'Abrir com...' e Associação de Aplicativos Padrão:**
  - Clique com o botão direito em arquivos para acessar o submenu dinâmico *"Abrir com"*, que lista os aplicativos compatíveis registrados no sistema (ex: VLC, MPV, LosslessCut para vídeos) com seus ícones nativos e marcação do padrão atual.
  - Abertura pontual rápida com qualquer aplicativo listado.
  - Diálogo *"Escolher outro aplicativo..."* com busca em tempo real de todos os aplicativos instalados, seleção de executáveis arbitrários e caixa de seleção *"Sempre usar este aplicativo para abrir arquivos .{ext}"*.
  - A definição de padrão sincroniza com o FreeDesktop (`xdg-mime`, `gio mime` e `~/.config/mimeapps.list`), garantindo que futuros duplos cliques abram automaticamente com o aplicativo escolhido.
- **Renomeação Inline Avançada (Estilo Double Commander):**
  - Acionada via `F2`.
  - Ciclo inteligente de seleção: 1º F2 seleciona o nome base sem extensão; 2º F2 seleciona a extensão sem o ponto; 3º F2 seleciona o nome completo.
  - Setas `Up` e `Down` durante a edição confirmam e avançam diretamente para renomear o item adjacente.
- **Motor de Regras de Cores (Filter2):**
  - Coloração visual de arquivos por extensão ou atributo (`#DIR`, `#Hidden`, executáveis, mídias, imagens, documentos, compactados).
  - Editor visual interativo em *Ferramentas -> Regras de Cores (Filter2)...* com seletor de cores nativo (`QColorDialog`), amostra em tempo real, adicionar, remover, subir/descer e persistência automática em `~/.config/qdir/color_rules.json`.
- **Integração com Temas do Sistema (Qt6 Settings / qt6ct):**
  - Detecção automática de temas do `qt6ct` (`Breeze`, paletas escuras como `darker.conf`, fontes do sistema e ícones).
- **Exportação:**
  - Exportação da lista de arquivos da pasta ativa para HTML estilizado, CSV estruturado ou TXT tabulado.
- **Compatibilidade de Sessões:**
  - Suporte a leitura de arquivos `.qdr` originais do Q-Dir e salvamento automático do estado em `~/.config/qdir/settings.json`.

---

## Instalação e Execução

### 1. Criar Ambiente Conda
```bash
conda env create -f environment.yml
conda activate qdir
```

### 2. Executar
```bash
python3 qdir_app.py
```
ou, com o atalho instalado no sistema:
```bash
qdir
```

---

## Licença

Desenvolvido para uso pessoal e open-source comunitário. Inspirado no software original Q-Dir de Nenad Hrg (SoftwareOK.com).
