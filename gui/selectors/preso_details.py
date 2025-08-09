from __future__ import annotations

from typing import Dict

from bs4 import BeautifulSoup


CADASTRO_URL = "https://canaime.com.br/sgp2rr/areas/unidades/cadastro.php?id_cad_preso={id}"
INFORMES_URL = "https://canaime.com.br/sgp2rr/areas/unidades/Informes_LER.php?id_cad_preso={id}"


def _clean_text(text: str) -> str:
    return " ".join((text or "").split())


def _safe_select_text(soup: BeautifulSoup, selector: str) -> str:
    try:
        el = soup.select_one(selector)
        return _clean_text(el.get_text(separator=" ")) if el else ""
    except Exception:
        return ""


def fetch_preso_cadastro(session, preso_id: str) -> Dict[str, str]:
    url = CADASTRO_URL.format(id=preso_id)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    return {
        "mae": _safe_select_text(soup, "tr:nth-child(3) .titulobk"),
        "pai": _safe_select_text(soup, "tr:nth-child(4) .titulobk"),
        "nascimento": _safe_select_text(soup, "tr:nth-child(5) .titulobk~ .titulobk"),
        "cpf": _safe_select_text(soup, "tr:nth-child(13) .titulobk~ .titulobk"),
        "cidade_origem": _safe_select_text(soup, "tr:nth-child(8) .titulobk"),
        "estado_origem": _safe_select_text(soup, "tr:nth-child(9) .titulobk"),
        "endereco": _safe_select_text(soup, "tr:nth-child(24) .titulobk"),
    }


def fetch_preso_informes(session, preso_id: str) -> Dict[str, str]:
    url = INFORMES_URL.format(id=preso_id)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    return {
        "cor_etnia": _safe_select_text(soup, "tr:nth-child(16) .titulobk:nth-child(2)"),
        "rosto": _safe_select_text(soup, "tr:nth-child(17) td.titulobk"),
        "olhos": _safe_select_text(soup, "tr:nth-child(18) td.titulobk"),
        "nariz": _safe_select_text(soup, "tr:nth-child(19) td.titulobk"),
        "boca": _safe_select_text(soup, ".titulobk~ .titulo12bk+ .titulobk"),
        "dentes": _safe_select_text(soup, "tr:nth-child(17) .tituloVerde .titulobk"),
        "cabelos": _safe_select_text(soup, "tr:nth-child(18) .tituloVerde .titulobk"),
        "altura": _safe_select_text(soup, "tr:nth-child(19) .tituloVerde .titulobk"),
        "sinais_particulares": _safe_select_text(soup, "tr:nth-child(22) .titulobk"),
    }


