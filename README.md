# QDir Linux (Quad Explorer)

Port nativo do clássico **Q-Dir** (SoftwareOK) para Linux, desenvolvido em **Python 3.12** e **PyQt6**.

Gerenciador de arquivos multilocular projetado para agilizar o fluxo de trabalho com até 4 painéis independentes, abas simultâneas, filtragem em tempo real, suporte total a temas do sistema e ampla compatibilidade.

---

## Principais Funcionalidades

- **12 Modos de Layout:**
  - 4-Quad (2x2)
  - 3-Tri (Topo / Embaixo, Esquerda / Direita)
  - 4 Colunas / 4 Linhas
  - 3 Colunas / 3 Linhas
  - 2-Dual (Vertical / Horizontal)
  - 1-Single (Painel Único)
- **Árvores de Diretórios:**
  - Sem árvore, 4 árvores individuais ou 1 árvore compartilhada na lateral esquerda.
- **Abas Independentes por Painel:**
  - Suporte a múltiplas abas, alternância automática ao passar o mouse com arrasto e fechamento com botão do meio.
- **Drag & Drop e Área de Transferência:**
  - Arrastar e soltar arquivos entre painéis e sobre abas (Copiar ou Mover).
  - Suporte completo a `Ctrl+C`, `Ctrl+X` (com atenuação visual translúcida de arquivos recortados) e `Ctrl+V` seguindo o padrão FreeDesktop / GNOME.
- **Navegação Inteligente:**
  - Entrada fixa `..` no topo para retornar à pasta pai (via `Enter` ou duplo clique).
  - Duplo clique abre arquivos no visualizador padrão ou navega em pastas.
  - `Backspace` para subir pasta.
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
