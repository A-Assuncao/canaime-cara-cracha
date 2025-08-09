## Changelog

Este arquivo documenta as mudanças relevantes do projeto. O formato segue a ideia do Keep a Changelog, com versões datadas.

### [0.1.0] - 2025-08-09

#### Adicionado
- Login automatizado no Canaimé com detecção de formulário e fallback de SSL (quando houver problema de certificado, repete sem verificação e informa no status).
- Scraping da PAMC com extração de:
  - Código (remove 3 primeiros caracteres da 1ª linha)
  - Nome (2ª linha)
  - Ala/Cela (remove 5 primeiros caracteres da 5ª linha; split no último '/')
  - Foto via `img[src]` com URL relativa resolvida
- Tela de seleção de alas:
  - Duas colunas, centralizada, fonte maior
  - Integração de comunicação entre processos para enviar a seleção ao processo de scraping
- Coleta de detalhes por preso:
  - `cadastro.php?id_cad_preso={id}`: Mãe, Pai, Nascimento, CPF, Cidade/Estado de Origem, Endereço
  - `Informes_LER.php?id_cad_preso={id}`: Cor/Etnia, Rosto, Olhos, Nariz, Boca, Dentes, Cabelos, Altura, Sinais Particulares
- Geração de PDF (cara‑crachá):
  - A4 com margens de 20 mm
  - Foto 70×90 mm à esquerda; dados à direita com títulos e quebra automática de linha
  - 1 preso por página
  - Nome sugerido do arquivo inclui as alas selecionadas e é escolhido via caixa de diálogo (topmost e centralizada)
- README atualizado com instruções, dados coletados, observações de SSL, troubleshooting e build opcional com PyInstaller
- `.gitignore` atualizado para ignorar `*.pdf` e `pamc_presos.json`
- `requirements.txt` com `Pillow` e `reportlab`

#### Alterado
- Título/subtítulo da janela passam a usar `APP_NAME` e `APP_VERSION` (fallbacks presentes quando módulos não existem)
- Fluxo de tratamento de erros: evita finalizar a UI antes de exibir mensagens vinda do processo filho

#### Removido
- Geração de JSON local com os resultados (não é mais salvo)



