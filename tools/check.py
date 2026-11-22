"""Checks for the probate article: length, reading level, title and meta lengths,
banned advertising words, em dashes, and that every outside link resolves.

Usage: python tools/check.py [--links]
Needs: beautifulsoup4, textstat (0.7.x)
"""
import json, re, sys, urllib.request
from pathlib import Path
from bs4 import BeautifulSoup
import textstat

page = Path(__file__).resolve().parent.parent / "docs" / "index.html"
soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
problems = []

title = soup.title.get_text()
meta = soup.find("meta", attrs={"name": "description"})["content"]
print(f"title: {len(title)} chars | meta description: {len(meta)} chars")
if len(title) > 60: problems.append("title over 60 characters")
if not 120 <= len(meta) <= 160: problems.append("meta description outside 120-160 characters")
if not soup.find("meta", attrs={"name": "robots", "content": "noindex"}): problems.append("missing noindex")

post = BeautifulSoup(str(soup.find("article", class_="post")), "html.parser")
for sel in ["h2", "h3", "section.sources", "caption", "thead"]:
    for el in post.select(sel): el.decompose()
# Leaf blocks only, so a list item that wraps paragraphs is not counted twice.
blocks = [el.get_text(" ", strip=True) for el in post.find_all(["p", "li", "td", "th", "summary"])
          if not el.find(["p", "li"])]
# Treat each block as its own sentence when it has no end punctuation (list items, table cells).
text = " ".join(b if b.endswith((".", "?", "!", ":")) else b + "." for b in blocks if b)
words = len(re.findall(r"[A-Za-z0-9$][\w$,.'-]*", text))
text = re.sub(r"§\s*", "section ", text)  # so the reading formulas see a word, not a symbol
print(f"article body words (no headings or sources): {words}")
print(f"Flesch-Kincaid grade: {textstat.flesch_kincaid_grade(text)}")
print(f"Flesch reading ease: {textstat.flesch_reading_ease(text)}")
print(f"SMOG: {textstat.smog_index(text)} | Dale-Chall: {textstat.dale_chall_readability_score(text)}")
full = soup.find("article", class_="post").get_text(" ", strip=True)
print(f"article words including headings, FAQ and sources: {len(full.split())}")

copy = soup.get_text(" ")
for w in ["expert", "specialist", "testimonial", "specialize", "guarantee", "best lawyer", "certified", " AI "]:
    hits = [m.start() for m in re.finditer(re.escape(w), copy, re.I)]
    if w in ("expert", "specialist", "testimonial") and hits:
        # Allowed only inside the writer's notes, where the rule itself is named.
        notes = soup.find("section", class_="notes").get_text(" ")
        if len(hits) > len(re.findall(re.escape(w), notes, re.I)): problems.append(f"'{w}' used outside the notes")
    elif hits:
        problems.append(f"banned word '{w.strip()}' found")
if "\u2014" in copy: problems.append("em dash in copy")

faq_schema = json.loads(soup.find("script", type="application/ld+json").string)
qs = [q["name"] for q in faq_schema["mainEntity"]]
page_qs = [s.get_text(strip=True) for s in soup.select(".faq summary")]
if qs != page_qs: problems.append("FAQ schema questions do not match the page")
for q in faq_schema["mainEntity"]:
    shown = [d.find("p").get_text(" ", strip=True) for d in soup.select(".faq details") if d.summary.get_text(strip=True) == q["name"]]
    if not shown or shown[0] != q["acceptedAnswer"]["text"]: problems.append(f"FAQ answer differs: {q['name']}")
print(f"FAQ questions: {len(qs)}")

links = sorted({a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("http")})
print(f"outside links: {len(links)}")
if "--links" in sys.argv:
    for url in links:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/130"})
        try:
            code = urllib.request.urlopen(req, timeout=20).status
        except Exception as e:
            code = getattr(e, "code", str(e))
        print(f"  {code}  {url}")
        if code != 200 and code != 403: problems.append(f"link failed: {url} ({code})")

print("OK" if not problems else "PROBLEMS:\n  " + "\n  ".join(problems))
sys.exit(1 if problems else 0)
