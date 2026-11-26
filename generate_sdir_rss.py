from datetime import datetime, timezone
import difflib
import hashlib
import html
import json
import os
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import requests

URL = "https://www.sdir.no/naringsfartoy/fartoystyper/lasteskip/lasteskip-med-storste-lengde-under-15-meter/lasteskip-under-8-meter/"
STATE_FILE = "sdir_page_state.json"
OUTPUT_XML = "sdir_lasteskip_under_8m.xml"
MAX_ENTRIES = 25


def load_state():
  if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  return {"last_hash": "", "last_lines": [], "entries": []}


def save_state(state):
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_clean_lines():
  headers = {"User-Agent": "Mozilla/5.0 (compatible; SdirMonitorBot/1.0)"}
  response = requests.get(URL, headers=headers, timeout=15)
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")
  main_content = soup.find("main") or soup

  # Remove navigation, headers, footers, and breadcrumbs so only body content is tracked
  for tag in main_content.find_all(["nav", "header", "footer", "script", "style"]):
    tag.decompose()

  lines = []
  for el in main_content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
    # Skip nested elements already captured by a parent
    if el.find_parent(["p", "li"]):
      continue
    text = " ".join(el.get_text(" ", strip=True).split())
    if text and text not in lines:
      lines.append(text)

  return lines


def format_diff_html(old_lines, new_lines):
  diff = difflib.ndiff(old_lines, new_lines)
  added = []
  removed = []

  for line in diff:
    if line.startswith("+ "):
      added.append(html.escape(line[2:]))
    elif line.startswith("- "):
      removed.append(html.escape(line[2:]))

  parts = ["<p>Endringer oppdaget på Sjøfartsdirektoratets side for <strong>Lasteskip under 8 meter</strong>:</p>"]

  if added:
    parts.append("<h3>Lagt til / Ny tekst:</h3><ul>")
    for item in added:
      parts.append(f"<li><strong>+</strong> {item}</li>")
    parts.append("</ul>")

  if removed:
    parts.append("<h3>Fjernet / Endret tekst:</h3><ul>")
    for item in removed:
      parts.append(f"<li><strong>-</strong> {item}</li>")
    parts.append("</ul>")

  if not added and not removed:
    parts.append("<p>Mindre tekst- eller rekkefølgeendring på siden.</p>")

  return "\n".join(parts)


def build_rss():
  state = load_state()
  current_lines = fetch_clean_lines()
  content_blob = "\n".join(current_lines)
  current_hash = hashlib.sha256(content_blob.encode("utf-8")).hexdigest()
  now = datetime.now(timezone.utc)

  if not state["last_hash"]:
    # Initial baseline snapshot
    state["last_hash"] = current_hash
    state["last_lines"] = current_lines
    state["entries"].insert(
        0,
        {
            "id": f"{URL}#{current_hash[:12]}",
            "title": f"Overvåking startet ({now.strftime('%Y-%m-%d')}) - Lasteskip under 8 meter",
            "summary": (
                "<p>Overvåking av regelverk og brødtekst på Sjøfartsdirektoratets side er aktivert.</p>"
                f"<p>Antall overvåkede tekstlinjer/punkter: {len(current_lines)}</p>"
            ),
            "pubDate": now.isoformat(),
        },
    )
    save_state(state)

  elif current_hash != state["last_hash"]:
    # Page content changed! Build diff summary
    diff_html = format_diff_html(state["last_lines"], current_lines)
    state["last_hash"] = current_hash
    state["last_lines"] = current_lines
    state["entries"].insert(
        0,
        {
            "id": f"{URL}#{current_hash[:12]}",
            "title": f"Endring oppdaget ({now.strftime('%Y-%m-%d')}) - Lasteskip under 8 meter",
            "summary": diff_html,
            "pubDate": now.isoformat(),
        },
    )
    state["entries"] = state["entries"][:MAX_ENTRIES]
    save_state(state)

  fg = FeedGenerator()
  fg.id(URL)
  fg.title("Endringsvarsel: Lasteskip under 8 meter (Sdir)")
  fg.link(href=URL, rel="alternate")
  fg.description("Varsler om endringer i brødtekst og regelverk for lasteskip under 8 meter hos Sjøfartsdirektoratet.")
  fg.language("no")

  for entry in reversed(state["entries"]):
    fe = fg.add_entry()
    fe.id(entry["id"])
    fe.title(entry["title"])
    fe.link(href=URL)
    fe.description(entry["summary"])
    fe.pubDate(datetime.fromisoformat(entry["pubDate"]))

  fg.rss_file(OUTPUT_XML, pretty=True)
  print(f"Updated {OUTPUT_XML} ({len(state['entries'])} entries).")


if __name__ == "__main__":
  build_rss()
