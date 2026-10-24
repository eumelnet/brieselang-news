"""Deterministic source adapters. No invented dates, no generated factual claims."""
import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from django.db import transaction
from django.utils import timezone
from .models import Source, Story, Revision

log = logging.getLogger(__name__)
USER_AGENT = "BrieselangNewsPilot/0.1 (+https://brieselang-news.e.mcsps.de/quellen/)"
SEEDS = [
    ("Gemeinde · Aktuelle Meldungen", "https://www.gemeindebrieselang.de/Aktuelles/Aktuelle-Meldungen.htm", "municipal", "dorfleben"),
    ("Gemeinde · Veranstaltungen", "https://www.gemeindebrieselang.de/Aktuelles/Veranstaltungen.htm", "events", "veranstaltungen"),
    ("Gemeinde · Straßensperrungen", "https://www.gemeindebrieselang.de/Aktuelles/Strassensperrungen.htm", "closures", "verkehr"),
    ("Neueroeffnung.info · Café Naschkatze", "https://www.neueroeffnung.info/brieselang/cafe-naschkatze_1", "opening", "neueroeffnungen"),
]


def clean(text):
    return re.sub(r"\s+", " ", text).strip()


def text(node):
    return clean(node.get_text(" ", strip=True)) if node else ""


def numeric_date(value):
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", value)
    if match:
        try:
            return datetime.strptime(match[1], "%d.%m.%Y").date()
        except ValueError:
            pass
    return None


def item(key, title, url, evidence, date_label="", source_date=None):
    return dict(external_id=key, title=title[:500], url=url, evidence=clean(evidence), date_label=date_label[:200], source_date=source_date)


def parse(source, html):
    soup = BeautifulSoup(html, "html.parser")
    if source.parser == "municipal":
        for node in soup.select("#content_frame .ac_teaser_item"):
            link = node.select_one("a.ac_teaser_link")
            title = text(node.select_one(".ac_teaser_title"))
            if not link or not title:
                continue
            url = urljoin(source.url, link["href"]).rstrip("?")
            date = text(node.select_one(".ac_teaser_date"))
            yield item(urlsplit(url).path, title, url, text(node.select_one(".ac_teaser_text")), date, numeric_date(date))
    elif source.parser == "events":
        for node in soup.select("#dwa_event_list_wrapper .event_wrapper"):
            link = node.select_one(".event_teaser_title_link")
            if not link:
                continue
            url = urljoin(source.url, link["href"]).rstrip("?")
            evidence = " ".join(filter(None, [text(node.select_one(".event_subtitle")), text(node.select_one(".event_teaser")), text(node.select_one(".event_place"))]))
            date = text(node.select_one(".event_date"))
            # The listing omits the year. Preserve its wording instead of guessing.
            yield item(urlsplit(url).path, text(link), url, evidence or text(link), date)
    elif source.parser == "closures":
        frame = soup.select_one("#content_frame")
        if not frame:
            return
        lines = [clean(x) for x in frame.get_text("\n", strip=True).splitlines() if clean(x)]
        dates = [i for i, line in enumerate(lines) if line.startswith("Veröffentlicht am:")]
        for n, pos in enumerate(dates):
            if pos == 0:
                continue
            end = dates[n + 1] - 1 if n + 1 < len(dates) else len(lines)
            title = lines[pos - 1]
            body_start = pos + 1
            date_text = lines[pos]
            if not numeric_date(date_text) and body_start < end:
                date_text += " " + lines[body_start]
                body_start += 1
            evidence = " ".join(x for x in lines[body_start:end] if not re.fullmatch(r"[-–—]+", x))
            # Publication date is stable even if the headline/end date changes.
            day = numeric_date(date_text)
            if day is None:
                raise ValueError("Publikationsdatum einer Sperrung fehlt")
            ordinal = sum(numeric_date(" ".join(lines[p:p + 2])) == day for p in dates[:n])
            key = f"closure:{day}:{ordinal}"
            yield item(key, title, source.url, evidence, date_text, day)
    elif source.parser == "opening":
        main = soup.select_one("main") or soup
        heading = main.find("h1")
        if not heading or "Naschkatze" not in text(heading):
            return
        lines = main.get_text("\n", strip=True).splitlines()
        start = next((i for i, x in enumerate(lines) if "Neueröffnung von Cafe Naschkatze" in x), None)
        end = next((i for i, x in enumerate(lines) if start is not None and i > start and "Öffnungszeiten" in x), None)
        if start is None or end is None:
            return
        evidence = clean(" ".join(lines[start + 1:end]))
        yield item("cafe-naschkatze", "Café Naschkatze: Neueröffnung in Brieselang", source.url, evidence, "Eröffnungstermine siehe Quelle")


def save_item(source, data):
    fingerprint = hashlib.sha256((data["title"] + data["evidence"] + data["date_label"]).encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        story, created = Story.objects.get_or_create(source=source, external_id=data["external_id"], defaults={**data, "category": source.category, "fingerprint": fingerprint, "summary": ""})
        changed = story.fingerprint != fingerprint
        if changed:
            for key, value in data.items():
                setattr(story, key, value)
            story.fingerprint = fingerprint
            story.revision_count += 1
            story.updated_at = now
        story.last_seen = now
        story.save()
        if changed or created:
            Revision.objects.create(story=story, title=story.title, evidence=story.evidence, fingerprint=fingerprint)
    return created, changed


def collect():
    for name, url, parser, category in SEEDS:
        Source.objects.get_or_create(url=url, defaults=dict(name=name, parser=parser, category=category))
    failures = 0
    with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        robots = {}
        for source in Source.objects.filter(enabled=True):
            source.last_attempt = timezone.now()
            try:
                parts = urlsplit(source.url)
                if parts.scheme != "https" or parts.hostname not in {"www.gemeindebrieselang.de", "www.neueroeffnung.info"}:
                    raise ValueError("Quelle benötigt einen freigegebenen HTTPS-Host und passenden Adapter")
                origin = f"{parts.scheme}://{parts.netloc}"
                if origin not in robots:
                    response = client.get(origin + "/robots.txt")
                    if response.status_code not in (404, 410):
                        response.raise_for_status()
                    policy = RobotFileParser()
                    policy.parse(response.text.splitlines() if response.is_success else [])
                    robots[origin] = policy
                if not robots[origin].can_fetch(USER_AGENT, source.url):
                    raise ValueError("Abruf durch robots.txt ausgeschlossen")
                response = client.get(source.url)
                response.raise_for_status()
                items = list(parse(source, response.text))
                if not items:
                    raise ValueError("Keine Meldungen erkannt; Quellformat prüfen")
                counts = [save_item(source, data) for data in items]
                source.last_success = timezone.now()
                source.last_error = ""
                source.item_count = len(items)
                log.info("%s: %d Meldungen, %d neu, %d geändert", source.name, len(items), sum(c for c, _ in counts), sum(c for _, c in counts))
            except Exception as exc:
                source.last_error = str(exc)[:1000]
                failures += 1
                log.exception("Quellabruf fehlgeschlagen: %s", source.name)
            source.save()
    return failures
