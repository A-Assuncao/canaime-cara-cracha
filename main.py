from __future__ import annotations

import json
import logging
import sys
from types import ModuleType
from urllib.parse import urljoin

import multiprocessing as mp
from typing import TYPE_CHECKING, Optional

import requests
import urllib3
from bs4 import BeautifulSoup
import tkinter as tk


def _ensure_fallback_modules() -> None:
    """Garante módulos mínimos de `config.config` (APP_VERSION) e `utils.logger` (Logger).
    Evita falhas se você ainda não tiver essas pastas/módulos no projeto.
    """
    # config.config with APP_VERSION
    try:
        from config.config import APP_VERSION  # type: ignore # noqa: F401
    except Exception:
        config_pkg = sys.modules.get("config") or ModuleType("config")
        sys.modules["config"] = config_pkg
        config_mod = ModuleType("config.config")
        setattr(config_mod, "APP_VERSION", "v0.1.0")
        setattr(config_mod, "APP_NAME", "Canaimé Cara-Crachá")
        sys.modules["config.config"] = config_mod

    # utils.logger with Logger
    try:
        from utils.logger import Logger  # type: ignore # noqa: F401
    except Exception:
        utils_pkg = sys.modules.get("utils") or ModuleType("utils")
        sys.modules["utils"] = utils_pkg

        class _FallbackLogger:
            _logger = None

            @classmethod
            def get_logger(cls) -> logging.Logger:
                if cls._logger is None:
                    logger = logging.getLogger("canaime")
                    logger.setLevel(logging.INFO)
                    if not logger.handlers:
                        handler = logging.StreamHandler(sys.stdout)
                        formatter = logging.Formatter(
                            "%(asctime)s - %(levelname)s - %(message)s"
                        )
                        handler.setFormatter(formatter)
                        logger.addHandler(handler)
                    cls._logger = logger
                return cls._logger

        logger_mod = ModuleType("utils.logger")
        setattr(logger_mod, "Logger", _FallbackLogger)
        sys.modules["utils.logger"] = logger_mod


_ensure_fallback_modules()


from gui.selectors.pamc_scraper import fetch_pamc_data  # noqa: E402
from gui.selectors.preso_details import fetch_preso_cadastro, fetch_preso_informes  # noqa: E402
from utils.pdf_builder import build_pdf  # noqa: E402
from gui.login.login_canaime import LoginApp  # noqa: E402

if TYPE_CHECKING:  # Tipos corretos para anotações
    from multiprocessing.queues import Queue as MpQueue
    from multiprocessing.synchronize import Event as MpEvent


LOGIN_URL = "https://canaime.com.br/sgp2rr/login/login_principal.php"
TARGET_URL = (
    "https://canaime.com.br/sgp2rr/areas/impressoes/UND_ChamadaFOTOS_todos2.php?id_und_prisional=PAMC"
)


def _discover_login_form(
    session: requests.Session, login_url: str, queue: 'MpQueue | None' = None
) -> tuple[str, dict, str]:
    """Descobre action e campos ocultos do formulário de login para compor o payload.
    Retorna (action_url, payload_base, form_html)
    """
    try:
        resp = session.get(login_url, timeout=30)
    except requests.exceptions.SSLError as e:
        # Fallback inseguro: desabilita verificação de certificado
        if queue:
            queue.put((
                "status",
                "Aviso: problema de certificado SSL detectado. Tentando conexão sem verificação (inseguro).",
            ))
        session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        resp = session.get(login_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    form = soup.find("form")
    if not form:
        # Sem form na página de login — possivelmente não exige login
        return login_url, {}, resp.text

    action = form.get("action") or login_url
    action_url = urljoin(login_url, action)

    payload: dict[str, str] = {}
    for inp in form.find_all("input"):
        name = inp.get("name")
        if not name:
            continue
        itype = (inp.get("type") or '').lower()
        if itype in ("hidden", "submit"):
            payload[name] = inp.get("value") or ""

    return action_url, payload, resp.text


def _fill_login_credentials(
    payload_base: dict[str, str], username: str, password: str, form_html: str
) -> tuple[dict[str, str], Optional[str], Optional[str]]:
    """Detecta nomes prováveis dos campos de usuário/senha na página e preenche no payload.
    Retorna (payload, username_field, password_field)
    """
    soup = BeautifulSoup(form_html, "html.parser")
    form = soup.find("form")
    username_candidates = [
        "usuario",
        "username",
        "login",
        "user",
        "usr",
    ]
    password_candidates = [
        "senha",
        "password",
        "passwd",
        "pass",
        "pwd",
    ]

    # Heurística: primeiro input type=password define o campo de senha
    password_name = None
    if form:
        pwd_input = form.find("input", {"type": "password"})
        if pwd_input and pwd_input.get("name"):
            password_name = pwd_input.get("name")

    # Heurística: primeiro input text/email para usuário
    username_name = None
    if form:
        user_input = form.find("input", {"type": ["text", "email"]})
        if user_input and user_input.get("name"):
            username_name = user_input.get("name")

    # Se não encontrado, usa dicionário de candidatos
    if not username_name and form:
        names = [i.get("name") for i in form.find_all("input") if i.get("name")]
        for cand in username_candidates:
            if cand in names:
                username_name = cand
                break

    if not password_name and form:
        names = [i.get("name") for i in form.find_all("input") if i.get("name")]
        for cand in password_candidates:
            if cand in names:
                password_name = cand
                break

    payload = dict(payload_base)
    if username_name:
        payload[username_name] = username
    if password_name:
        payload[password_name] = password

    # Fallback absoluto: tenta pares comuns além das heurísticas
    for ukey in username_candidates:
        payload.setdefault(ukey, username)
    for pkey in password_candidates:
        payload.setdefault(pkey, password)

    return payload, username_name, password_name


def process_task_func(
    headless: bool,
    queue: 'MpQueue',
    command_queue: 'MpQueue',
    stop_event: 'MpEvent',
    username: str,
    password: str,
) -> None:
    """Executa login + scraping no processo separado e envia mensagens para a UI."""
    try:
        queue.put(("status", "Iniciando sessão..."))
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Referer": LOGIN_URL,
        })

        # Descobre formulário e payload base
        action_url, payload_base, form_html = _discover_login_form(session, LOGIN_URL, queue)
        queue.put(("status", f"Form action: {action_url}"))
        payload, user_field, pwd_field = _fill_login_credentials(payload_base, username, password, form_html)
        queue.put(("status", f"Campos detectados -> usuário: {user_field or 'desconhecido'}, senha: {pwd_field or 'desconhecido'}"))

        queue.put(("status", "Enviando credenciais..."))
        try:
            resp_post = session.post(action_url, data=payload, timeout=30, allow_redirects=True)
        except requests.exceptions.SSLError:
            if session.verify is not False:
                if queue:
                    queue.put((
                        "status",
                        "Aviso: problema de certificado no POST. Repetindo sem verificação (inseguro).",
                    ))
                session.verify = False
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            resp_post = session.post(action_url, data=payload, timeout=30, allow_redirects=True)
        resp_post.raise_for_status()
        queue.put(("status", f"Após login, URL atual: {resp_post.url}"))

        # Tenta acessar a página alvo
        queue.put(("status", "Acessando a página da PAMC..."))
        try:
            presos = fetch_pamc_data(session, TARGET_URL)
        except requests.exceptions.SSLError:
            if session.verify is not False:
                if queue:
                    queue.put((
                        "status",
                        "Aviso: problema de certificado ao acessar a PAMC. Repetindo sem verificação (inseguro).",
                    ))
                session.verify = False
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        presos = fetch_pamc_data(session, TARGET_URL)
        queue.put(("status", f"Blocos '.titulobkSingCAPS' encontrados: {len(presos)}"))

        # Descobrir todas as alas disponíveis
        alas_disponiveis = sorted({p.get("ala", "") for p in presos if p.get("ala")})
        queue.put(("choose_alas", alas_disponiveis))

        # Aguardar seleção do usuário via command_queue
        queue.put(("status", "Aguardando seleção de alas pelo usuário..."))
        selected_alas: list[str] = []
        while True:
            try:
                cmd, payload = command_queue.get(timeout=1.0)
                if cmd == "selected_alas":
                    selected_alas = list(payload or [])
                    break
            except Exception:
                if stop_event.is_set():
                    return
                continue

        queue.put(("status", f"Processando alas selecionadas: {', '.join(selected_alas)}"))

        # Filtrar presos pelas alas escolhidas
        presos_filtrados = [p for p in presos if p.get("ala") in selected_alas]
        queue.put(("status", f"Total de presos nas alas selecionadas: {len(presos_filtrados)}"))

        # Coletar detalhes para cada preso
        resultados: list[dict] = []
        for idx, preso in enumerate(presos_filtrados, 1):
            if stop_event.is_set():
                break
            pid = preso.get("id", "").strip()
            if not pid:
                continue
            queue.put(("status", f"[{idx}/{len(presos_filtrados)}] Buscando detalhes do preso {pid}..."))
            try:
                det_a = fetch_preso_cadastro(session, pid)
                det_b = fetch_preso_informes(session, pid)
                preso_full = {**preso, **det_a, **det_b}
                resultados.append(preso_full)
            except requests.exceptions.SSLError:
                if session.verify is not False:
                    queue.put(("status", "Aviso: SSL nos detalhes. Repetindo sem verificação."))
                    session.verify = False
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    det_a = fetch_preso_cadastro(session, pid)
                    det_b = fetch_preso_informes(session, pid)
                    preso_full = {**preso, **det_a, **det_b}
                    resultados.append(preso_full)
            except Exception as e:
                queue.put(("status", f"Falha ao coletar detalhes do preso {pid}: {e}"))

        # Perguntar caminho de salvamento do PDF (UI responde via command_queue)
        alas_tag = "_".join(a.replace("/", "-").replace(" ", "-") for a in selected_alas)[:60]
        suggested_pdf = f"cara_cracha_{alas_tag or 'todas'}.pdf"
        queue.put(("ask_save_path", suggested_pdf))
        save_path = ""
        queue.put(("status", "Aguardando local para salvar o PDF..."))
        while True:
            try:
                cmd, payload = command_queue.get(timeout=1.0)
                if cmd == "save_path":
                    save_path = (payload or "").strip()
                    break
            except Exception:
                if stop_event.is_set():
                    return
                continue

        if not save_path:
            queue.put(("status", "Operação cancelada: caminho não informado."))
            queue.put(("success", "Processo concluído sem gerar PDF."))
            queue.put(("exit_app", "Finalizado."))
            return

        # Gerar PDF
        try:
            queue.put(("status", f"Gerando PDF em '{save_path}'..."))
            build_pdf(session, resultados, save_path)
            queue.put(("status", f"PDF gerado: {save_path}"))
        except Exception as e:
            queue.put(("status", f"Falha ao gerar PDF: {e}"))

        # Se não encontrou nada, possivelmente login falhou
        if not presos:
            queue.put(("status", "Nenhum registro encontrado. Verificando se a sessão está autenticada..."))
            # Heurística simples: página alvo contém a palavra 'login'?
            check_resp = session.get(TARGET_URL, timeout=30)
            check_resp.raise_for_status()
            if "login" in check_resp.url.lower() or "login" in check_resp.text.lower():
                raise RuntimeError("Falha no login: verifique usuário/senha ou alterações no formulário.")

        queue.put(("success", "Coleta concluída com sucesso e PDF gerado."))
        queue.put(("exit_app", "Finalizado com sucesso."))

    except Exception as exc:
        import traceback

        tb = traceback.format_exc()
        # Enfileira o erro para a UI tratar e NÃO sinaliza o stop_event aqui,
        # para permitir que a UI consuma a mensagem de erro antes de encerrar.
        queue.put(("error", str(exc), tb))


def main() -> None:
    mp.freeze_support()
    root = tk.Tk()
    app = LoginApp(root=root, headless=False, process_task_func=process_task_func)
    root.mainloop()


if __name__ == "__main__":
    main()


