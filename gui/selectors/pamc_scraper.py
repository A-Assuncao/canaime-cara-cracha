from __future__ import annotations

from typing import List, Dict, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup


TARGET_URL = (
    "https://canaime.com.br/sgp2rr/areas/impressoes/UND_ChamadaFOTOS_todos2.php?id_und_prisional=PAMC"
)


def _resolve_image_link(tag, base_url: Optional[str]) -> str:
    """Tenta resolver o link de imagem associado ao bloco informado.
    Prioriza atributo 'src'. Se relativo, faz urljoin com base_url.
    Procura na seguinte ordem: o próprio bloco, o pai, irmãos anteriores e seguintes.
    """
    candidates = []
    # Dentro do próprio bloco
    candidates.append(tag.find("img"))
    # No pai
    if tag.parent:
        candidates.append(tag.parent.find("img"))
    # Irmão anterior e seguinte diretos
    if tag.previous_sibling and getattr(tag.previous_sibling, 'find', None):
        candidates.append(tag.previous_sibling.find("img"))
    if tag.next_sibling and getattr(tag.next_sibling, 'find', None):
        candidates.append(tag.next_sibling.find("img"))

    for img in candidates:
        if img is None:
            continue
        raw = img.get("src") or img.get("link") or ""
        if not raw:
            continue
        if base_url and not raw.lower().startswith(("http://", "https://")):
            return urljoin(base_url, raw)
        return raw
    return ""


def parse_pamc_html(html: str, base_url: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Faz o parsing do HTML da página de chamadas da PAMC.

    Regras de extração para cada bloco com classe `.titulobkSingCAPS`:
    - Linha 1: id (remover os 3 primeiros caracteres)
    - Linha 2: nome
    - Linha 3: ignorar
    - Linha 4: ignorar
    - Linha 5: "Ala/Cela" (remover os 5 primeiros caracteres); split pelo último '/'
    - Imagem: atributo 'link' da tag <img> (fallback para 'src')
    """

    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.select(".titulobkSingCAPS")

    prisoners: List[Dict[str, str]] = []

    for block in blocks:
        # Coleta e normaliza as linhas de texto
        text = block.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        prisoner_id = ""
        prisoner_name = ""
        ala = ""
        cela = ""

        if len(lines) >= 1:
            first_line = lines[0]
            prisoner_id = first_line[3:] if len(first_line) > 3 else first_line

        if len(lines) >= 2:
            prisoner_name = lines[1]

        if len(lines) >= 5:
            ala_cela_raw = lines[4]
            # Remover os 5 primeiros caracteres (ex.: "Ala: ")
            ala_cela_trimmed = ala_cela_raw[5:] if len(ala_cela_raw) > 5 else ala_cela_raw
            # Separar pelo último '/'
            parts = ala_cela_trimmed.rsplit("/", 1)
            if len(parts) == 2:
                ala = parts[0].strip()
                cela = parts[1].strip()
            else:
                ala = ala_cela_trimmed.strip()
                cela = ""

        # Obter link da imagem associado ao bloco (prioriza 'src')
        img_link = _resolve_image_link(block, base_url)

        prisoners.append(
            {
                "id": prisoner_id,
                "nome": prisoner_name,
                "ala": ala,
                "cela": cela,
                "imagem_link": img_link,
            }
        )

    return prisoners


def fetch_pamc_data(session, target_url: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Usa uma sessão autenticada (requests.Session) para buscar a página da PAMC
    e retorna a lista de presos parseada via `parse_pamc_html`.
    """
    url = target_url or TARGET_URL
    response = session.get(url)
    response.raise_for_status()
    return parse_pamc_html(response.text, base_url=url)


