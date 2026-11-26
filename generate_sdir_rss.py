from datetime import datetime, timezone
import json
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
import requests

URL = "https://www.sdir.no/naringsfartoy/fartoystyper/lasteskip/lasteskip-med-storste-lengde-under-15-meter/lasteskip-under-8-meter/"
STATE_FILE = "sdir_seen_items.json"
OUTPUT_XML = "sdir_lasteskip_under_8m.xml"


def load_state():
  if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
      return json.load(f)
  return {}


def save_state(state):
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_items():
  headers = {"User-Agent": "Mozilla/5.0 (compatible; SdirRSSBot/1.0)"}
  response = requests.get(URL, headers=headers, timeout=15)
  response.raise_for_status()

  soup = BeautifulSoup(response.text, "html.parser")
  main_content = soup.find("main") or soup

  items = []
  # Target links inside bullet lists within the main content area
  for ul in main_content.find_all("ul"):
    # Skip navigation/breadcrumb lists
    if ul.find_parent(["nav", "header", "footer"]):
      continue
    for li in ul.find_all("li", recursive=False):
      link = li.find("a", href=True)
      if link:
        title = " ".join(link.get_text().split())
        full_url = urljoin(URL, link["href"])
        items.append({"title": title, "link": full_url})
  return items


def build_rss():
  state = load_state()
  current_items = fetch_items()
  now_iso = datetime.now(timezone.utc).isoformat()
  updated = False

  for item in current_items:
    key = item["link"]
    if key not in state:
      state[key] = {
          "title": item["title"],
          "link": item["link"],
          "pubDate": now_iso,
      }
      updated = True
    elif state[key]["title"] != item["title"]:
      # Update title if the regulation text changed
      state[key]["title"] = item["title"]
      updated = True

  if updated or not os.path.exists(OUTPUT_XML):
    save_state(state)

  fg = FeedGenerator()
  fg.id(URL)
  fg.title("Lasteskip under 8 meter - Sjøfartsdirektoratet")
  fg.link(href=URL, rel="alternate")
  fg.description(
      "Krav og regelverk som gjelder for lasteskip med største lengde under 8"
      " meter."
  )
  fg.language("no")

  # Sort items newest first based on when they were first detected
  sorted_entries = sorted(
      state.values(), key=lambda x: x["pubDate"], reverse=True
  )

  for entry in sorted_entries:
    fe = fg.add_entry()
    fe.id(entry["link"])
    fe.title(entry["title"])
    fe.link(href=entry["link"])
    fe.pubDate(datetime.fromisoformat(entry["pubDate"]))

  fg.rss_file(OUTPUT_XML, pretty=True)
  print(f"Generated {OUTPUT_XML} with {len(sorted_entries)} items.")


if __name__ == "__main__":
  build_rss()
