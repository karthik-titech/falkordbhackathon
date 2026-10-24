"""Batch research public professional speaker pages into the event graph.

Only manifest ``professional_urls`` are fetched. Personal social profile URLs
are always excluded; this script never reads LinkedIn/X fields from the input.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
import argparse
import hashlib
import ipaddress
import json
import re
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from warmopen.graphstore import GraphStore


MAX_BYTES = 2 * 1024 * 1024
MAX_TEXT = 100_000
MAX_EXCERPT = 1000
TIMEOUT = 12
MAX_WORKERS = 6
SOCIAL_HOSTS = {
    "linkedin.com", "facebook.com", "instagram.com", "x.com", "twitter.com",
    "tiktok.com", "threads.net", "snapchat.com", "youtube.com", "youtu.be",
}
BOILERPLATE_TAGS = {"script", "style", "nav", "footer", "header", "menu", "form", "noscript", "svg"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
BOILERPLATE_MARKERS = re.compile(r"cookie|consent|navigation|navbar|breadcrumb|site-menu|site-header|site-footer", re.I)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored_stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.ignored_stack:
            if tag not in VOID_TAGS:
                self.ignored_stack.append(tag)
            return
        attr_map = {key.lower(): value or "" for key, value in attrs}
        markers = " ".join(attr_map.get(key, "") for key in ("id", "class", "aria-label", "role", "data-testid"))
        if tag in BOILERPLATE_TAGS or BOILERPLATE_MARKERS.search(markers):
            if tag not in VOID_TAGS:
                self.ignored_stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        return

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.ignored_stack:
            index = len(self.ignored_stack) - 1 - self.ignored_stack[::-1].index(tag)
            del self.ignored_stack[index:]

    def handle_data(self, data):
        if not self.ignored_stack and data.strip():
            self.parts.append(data.strip())


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_http_url(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 or c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower().rstrip(".")
        _ = parsed.port
        if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        if host in SOCIAL_HOSTS or any(host.endswith("." + domain) for domain in SOCIAL_HOSTS):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            if host.replace(".", "").isdigit():
                return False
            try:
                addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
            except OSError:
                return False
            if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
                return False
        return True
    except (ValueError, OSError):
        return False


def _fetch(url):
    if not _public_http_url(url):
        return {"ok": False, "reason": "rejected_url"}
    request = Request(url, headers={"User-Agent": "WarmOpenPublicResearch/1.0", "Accept": "text/html"})
    try:
        with build_opener(_NoRedirect).open(request, timeout=TIMEOUT) as response:
            final_url = response.geturl()
            content_type = response.headers.get_content_type()
            if final_url != url or not _public_http_url(final_url) or content_type not in ("text/html", "application/xhtml+xml"):
                return {"ok": False, "reason": "not_html_or_redirected"}
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                return {"ok": False, "reason": "too_large"}
            encoding = response.headers.get_content_charset() or "utf-8"
            html = raw.decode(encoding, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {"ok": False, "reason": "fetch_failed"}
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return {"ok": False, "reason": "parse_failed"}
    text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()[:MAX_TEXT]
    return {"ok": bool(text), "text": text, "reason": "" if text else "empty_page"}


def _tokens(value):
    return [token.casefold() for token in re.findall(r"[\w'-]+", value, flags=re.UNICODE)
            if len(token) > 1]


def _name_verified(name, text):
    required = set(_tokens(name))
    normalized_name = " ".join(_tokens(name))
    normalized_text = " " + " ".join(_tokens(text)) + " "
    return len(required) >= 2 and f" {normalized_name} " in normalized_text


def _professional_text(text):
    text = re.sub(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", "", text)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d(). -]{7,}\d)(?!\w)", "", text)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    relevant = [sentence for sentence in sentences if re.search(
        r"\b(?:engineer\w*|develop\w*|research\w*|software|architect\w*|founder|"
        r"technology|technical|computer|platform\w*|data\w*|security|cloud|"
        r"agent\w*|AI|product|design\w*|manager|open.source|speaker|author|"
        r"GitHub|Microsoft|Amazon|Google|project\w*|code|programming)\b", sentence, re.I)]
    return " ".join(relevant).strip()


def _excerpt(name, text, topic_names):
    tokens = _tokens(name)
    lower = text.casefold()
    positions = [lower.find(name.casefold())] if name.casefold() in lower else []
    if not positions and tokens:
        positions = [lower.find(tokens[0])] if lower.find(tokens[0]) >= 0 else []
    center = min(positions) if positions else 0
    start = max(0, center - 240)
    excerpt = text[start:start + MAX_EXCERPT].strip()
    if start:
        excerpt = "…" + excerpt
    if start + MAX_EXCERPT < len(text):
        excerpt += "…"
    return _professional_text(excerpt)


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _manifest_rows(path):
    with open(path, "r", encoding="utf-8") as handle:
        rows = json.load(handle)
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Manifest must be a bounded list")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("name"), str):
            raise ValueError("Manifest row identity is invalid")
        if row["id"] in seen or not row["id"] or not row["name"].strip():
            raise ValueError("Manifest contains a duplicate or empty identity")
        seen.add(row["id"])
        if row.get("profile_scrape_consent") is True:
            raise ValueError("This batch is restricted to non-social professional URLs")
        urls = row.get("professional_urls", [])
        if not isinstance(urls, list) or len(urls) > 12 or any(not isinstance(url, str) for url in urls):
            raise ValueError("Manifest professional URL list is invalid")
    return rows


def _load_topics(store, conference_ids):
    rows = store.query(store.event(), "MATCH (t:Topic) RETURN t.id, t.name").result_set
    topics = {}
    for topic_id, name in rows:
        if isinstance(topic_id, str) and isinstance(name, str) and name.strip():
            topics[topic_id] = name.strip()
    allowed = set()
    for conference_id in conference_ids:
        rows = store.query(
            store.event(),
            "MATCH (:Person)-[s:SPEAKS_AT]->(talk:Talk)-[a:ABOUT]->(topic:Topic) "
            "WHERE talk.conference = $conference RETURN DISTINCT topic.id",
            {"conference": conference_id}).result_set
        allowed.update(row[0] for row in rows if row and isinstance(row[0], str))
    return topics, allowed


def _topics_for_text(text, topics, allowed):
    normalized = f" {text.casefold()} "
    found = []
    for topic_id in sorted(allowed):
        name = topics.get(topic_id)
        if not name:
            continue
        needle = name.casefold().strip()
        if needle and re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", normalized):
            found.append(topic_id)
    return found


def research_profiles(store, manifest_path, report_path=None):
    rows = _manifest_rows(manifest_path)
    conference_ids = sorted({conference for row in rows for conference in row.get("conference_ids", [])
                             if isinstance(conference, str)})
    people = store.query(store.event(), "MATCH (p:Person) RETURN p.id, p.name").result_set
    people_by_id = {person_id: name for person_id, name in people if isinstance(person_id, str)}
    topic_names, allowed_topic_ids = _load_topics(store, conference_ids)

    # Fetch every unique eligible URL once, with a strict concurrency ceiling.
    url_people = {}
    for row in rows:
        for url in dict.fromkeys(row.get("professional_urls", [])):
            if _public_http_url(url):
                url_people.setdefault(url, []).append(row["id"])
    fetched = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        pending = {executor.submit(_fetch, url): url for url in url_people}
        for future in as_completed(pending):
            url = pending[future]
            try:
                fetched[url] = future.result()
            except Exception:
                fetched[url] = {"ok": False, "reason": "fetch_failed"}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = {}
    event = store.event()
    for row in rows:
        person_id, name = row["id"], row["name"].strip()
        if person_id not in people_by_id:
            report[person_id] = {"status": "person_missing", "source_count": 0, "topic_count": 0}
            continue
        if set(_tokens(people_by_id[person_id] or "")) != set(_tokens(name)):
            report[person_id] = {"status": "identity_mismatch", "source_count": 0, "topic_count": 0}
            continue
        source_types = {
            source.get("url"): source.get("type")
            for source in row.get("sources", [])
            if isinstance(source, dict) and isinstance(source.get("url"), str)
        }
        verified = []
        fetched_any = False
        for url in dict.fromkeys(row.get("professional_urls", [])):
            result = fetched.get(url, {"ok": False})
            if not result.get("ok"):
                continue
            fetched_any = True
            if _name_verified(name, result["text"]):
                verified.append((url, result["text"], source_types.get(url)))

        if any(source_type == "professional_bio_or_employer" for _url, _text, source_type in verified):
            status = "complete"
        elif verified:
            status = "conference_only"
        else:
            status = "unavailable"
        all_topic_ids = set()
        source_count = 0
        for url, text, source_type in verified:
            is_bio_source = source_type == "professional_bio_or_employer"
            excerpt = _excerpt(name, text, [])
            relevant_topics = (_topics_for_text(excerpt, topic_names, allowed_topic_ids)
                               if is_bio_source else [])
            all_topic_ids.update(relevant_topics)
            evidence_id = "github-profile-evidence:" + _digest(person_id + "\0" + url + "\0" + excerpt)
            profile_id = "github-professional-profile:" + _digest(person_id + "\0" + url)
            if is_bio_source:
                claim = f"Public professional biography for {name} provides this context: {excerpt}"
            else:
                claim = f"Public conference page names {name} in this context: {excerpt}"
            props = {"id": evidence_id, "url": url, "claim": claim,
                     "observed_at": now, "visibility": "public"}
            store.query(event, "MERGE (e:Evidence {id: $id}) SET e += $props",
                        {"id": evidence_id, "props": props})
            store.query(event,
                        "MATCH (p:Person {id: $person}), (e:Evidence {id: $evidence}) "
                        "MERGE (p)-[:SUPPORTED_BY {evidence_id: $evidence}]->(e)",
                        {"person": person_id, "evidence": evidence_id})
            if is_bio_source:
                store.query(event,
                            "MERGE (profile:ProfessionalProfile {id: $id}) "
                            "SET profile.person_id = $person, profile.url = $url, "
                            "profile.researched_at = $observed, profile.source_type = 'public_professional_bio'",
                            {"id": profile_id, "person": person_id, "url": url, "observed": now})
                store.query(event,
                            "MATCH (p:Person {id: $person}), (profile:ProfessionalProfile {id: $id}) "
                            "MERGE (p)-[:HAS_PROFILE {evidence_id: $evidence}]->(profile)",
                            {"person": person_id, "id": profile_id, "evidence": evidence_id})
            for topic_id in relevant_topics:
                topic_evidence_id = "github-profile-topic:" + _digest(person_id + "\0" + url + "\0" + topic_id)
                topic_claim = f"Public professional page for {name} discusses the conference topic {topic_names[topic_id]}: {excerpt}"
                topic_props = {"id": topic_evidence_id, "url": url, "claim": topic_claim,
                               "observed_at": now, "visibility": "public"}
                store.query(event, "MERGE (e:Evidence {id: $id}) SET e += $props",
                            {"id": topic_evidence_id, "props": topic_props})
                store.query(event,
                            "MATCH (p:Person {id: $person}), (t:Topic {id: $topic}) "
                            "MERGE (p)-[r:INTERESTED_IN {evidence_id: $evidence}]->(t)",
                            {"person": person_id, "topic": topic_id, "evidence": topic_evidence_id})
                store.query(event,
                            "MATCH (p:Person {id: $person}), (e:Evidence {id: $evidence}) "
                            "MERGE (p)-[:SUPPORTED_BY {evidence_id: $evidence}]->(e)",
                            {"person": person_id, "evidence": topic_evidence_id})
            source_count += 1
        store.query(event,
                    "MATCH (p:Person {id: $id}) SET p.professional_profile_research_status = $status, "
                    "p.professional_profile_researched_at = $observed, p.professional_profile_source_count = $count",
                    {"id": person_id, "status": status, "observed": now, "count": source_count})
        report[person_id] = {"status": status, "source_count": source_count,
                             "topic_count": len(all_topic_ids)}

    result = {"researched_at": now, "people": report,
              "counts": {status: sum(item["status"] == status for item in report.values())
                         for status in ("complete", "conference_only", "unavailable", "person_missing", "identity_mismatch")}}
    if report_path:
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Research manifest professional URLs into the public event graph")
    parser.add_argument("manifest")
    parser.add_argument("--report", default="/tmp/github-profile-research-report.json")
    args = parser.parse_args(argv)
    try:
        rows = _manifest_rows(args.manifest)
        store = GraphStore.connect()
        result = research_profiles(store, args.manifest, args.report)
    except Exception:
        print("Professional profile research failed before completion.", file=sys.stderr)
        return 2
    print(json.dumps({"people": len(rows), "counts": result["counts"], "report": args.report}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
