## Canaimé — Cara‑Crachá PAMC

Aplicativo desktop (Tkinter) para autenticar no Canaimé, listar presos da PAMC, permitir a seleção de alas e gerar um PDF cara‑crachá (1 preso por página) com foto e dados essenciais, pronto para conferência em papel A4.

### Funcionalidades
- **Login automatizado** no Canaimé, com detecção de formulário e tratamento de SSL (fallback inseguro quando necessário).
- **Lista de presos da PAMC** com extração de: Código, Nome, Ala, Cela e Foto.
- **Seleção de alas em duas colunas**, janela centralizada e fonte maior para leitura.
- **Coleta detalhada por preso** em páginas internas: cadastro e informes.
- **Geração de PDF** bem formatado: margens A4, foto ajustada (70×90 mm) e textos com quebra automática.

### Requisitos
- **Python**: 3.10+ (testado no Windows 10/11; funciona com 3.13).
- **Dependências**: instaladas via `requirements.txt`.

### Instalação
1) Opcional, crie um ambiente virtual:
```bash
python -m venv venv
venv\Scripts\activate
```
2) Instale as dependências:
```bash
python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements.txt
```
3) (Opcional) Gerar executável com PyInstaller:
```bash
pip install pyinstaller
pyinstaller --clean --noconfirm canaime_cara_cracha.spec
dist/canaime-cara-cracha/canaime-cara-cracha.exe
```

### Como usar
1) Execute o app:
```bash
python main.py
```
2) Faça login com seu usuário/senha do Canaimé.
3) Selecione uma ou mais alas na janela (duas colunas) e confirme.
4) Escolha onde salvar o PDF (janela de salvar é centralizada e fica em primeiro plano).
5) Aguarde a conclusão. O PDF será salvo no local escolhido.

### O que é coletado
- Página de listagem (PAMC):
  - 1ª linha: **Código** (remove os 3 primeiros caracteres)
  - 2ª linha: **Nome**
  - 5ª linha: **Ala/Cela** (remove os 5 primeiros caracteres; split no último '/')
  - **Foto**: `img[src]` com URL resolvida
- Página de cadastro (`cadastro.php?id_cad_preso={id}`):
  - **Mãe**, **Pai**, **Nascimento**, **CPF**, **Cidade Origem**, **Estado Origem**, **Endereço**
- Página de informes (`Informes_LER.php?id_cad_preso={id}`):
  - **Cor/Etnia**, **Rosto**, **Olhos**, **Nariz**, **Boca**, **Dentes**, **Cabelos**, **Altura**, **Sinais Particulares**

### PDF
- A4 com margens de 20 mm
- Foto à esquerda (70×90 mm), dados à direita; títulos e quebra de linha automática
- Nome sugerido: `cara_cracha_<ALAS>.pdf` (pode ser alterado ao salvar)

### Estrutura do projeto
- `main.py`: ponto de entrada; orquestra login, seleção de alas, scraping detalhado e geração do PDF. Comunicação GUI↔processo via filas.
- `gui/login/login_canaime.py`: GUI Tkinter (login, logs, seleção de alas, diálogo de salvar).
- `gui/selectors/pamc_scraper.py`: scraping da página da PAMC (lista de presos) e parser das linhas.
- `gui/selectors/preso_details.py`: coleta detalhes de cada preso nas duas páginas internas.
- `utils/pdf_builder.py`: montagem do PDF com layout de cara‑crachá.
- `.gitignore`: ignora `venv/`, artefatos (`*.pdf`), caches e arquivos de IDE.

### Observações de SSL
Se houver erro de certificado no host do Canaimé, o app repete as requisições com verificação desativada e informa no status (modo inseguro). Em ambientes controlados, prefira corrigir a cadeia de certificados do sistema.

### Troubleshooting
- `ModuleNotFoundError: No module named 'PIL'` → instale com `pip install -r requirements.txt`
- Falha de SSL → ver acima (fallback inseguro) ou corrija certificados raiz
- Falha de login → confirme credenciais; se o nome dos inputs mudar, adapte seletores
- Nenhum preso encontrado → o HTML pode ter mudado; ajuste seletores em `gui/selectors/*.py`

### Configuração opcional
- `config.config`: pode expor `APP_NAME` e `APP_VERSION` para serem exibidos na janela (há fallbacks no código quando ausentes).
- `utils.logger`: pode definir um `Logger` customizado. Há fallback simples se o módulo não existir.

### Licença
Consulte o arquivo `LICENSE` na raiz do repositório.
