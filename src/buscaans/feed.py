"""Geração do feed RSS 2.0 a partir do estado."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path


def _rfc822(iso: str) -> str:
    return format_datetime(datetime.fromisoformat(iso))


def descricao(item: dict) -> str:
    prefixo = f"Publicado no DOU em {datetime.fromisoformat(item['dou']):%d/%m/%Y}. " if item.get("dou") else ""
    return prefixo + (item.get("ementa") or "")


def montar(itens: list[dict], cfg_feed: dict) -> str:
    """itens: registros do estado (não excluídos), já ordenados do mais recente para o mais antigo."""
    rss = ET.Element("rss", version="2.0")
    canal = ET.SubElement(rss, "channel")
    ET.SubElement(canal, "title").text = cfg_feed["titulo"]
    ET.SubElement(canal, "link").text = cfg_feed["link"]
    ET.SubElement(canal, "description").text = cfg_feed["descricao"]
    ET.SubElement(canal, "language").text = cfg_feed["idioma"]
    if itens:
        # Data da última novidade, e não da execução, para o arquivo só mudar quando houver item novo.
        ET.SubElement(canal, "lastBuildDate").text = _rfc822(max(i["visto_em"] for i in itens))
    for i in itens:
        e = ET.SubElement(canal, "item")
        ET.SubElement(e, "title").text = i["titulo"]
        ET.SubElement(e, "link").text = i["link"]
        ET.SubElement(e, "guid", isPermaLink="true").text = i["link"]
        ET.SubElement(e, "description").text = descricao(i)
        ET.SubElement(e, "pubDate").text = _rfc822(i["visto_em"])
        if i.get("dou"):
            ET.SubElement(e, "category").text = f"DOU {datetime.fromisoformat(i['dou']):%d/%m/%Y}"
        if i.get("status"):
            ET.SubElement(e, "category").text = i["status"]
    ET.indent(rss)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def gravar(texto: str, arquivo: Path) -> bool:
    if arquivo.exists() and arquivo.read_text(encoding="utf-8") == texto:
        return False
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8", newline="\n")
    return True
