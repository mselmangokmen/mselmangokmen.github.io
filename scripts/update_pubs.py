"""
Fetch publications from Google Scholar and update index.html automatically.
Uses the scholarly library to scrape the Google Scholar profile.
"""

import json
import re
import os
from scholarly import scholarly

SCHOLAR_ID = "f2XKEDQAAAAJ"
INDEX_HTML = os.path.join(os.path.dirname(__file__), "..", "index.html")
PUBS_JSON = os.path.join(os.path.dirname(__file__), "..", "publications.json")

# Manual overrides: map paper titles to preferred URLs, extra tags, etc.
# Add entries here if you want a specific paper to link to a specific URL
MANUAL_LINKS = {}


def fetch_publications():
    """Fetch all publications from Google Scholar profile."""
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["publications"])

    pubs = []
    for pub in author.get("publications", []):
        # Fill in details for each publication
        try:
            filled = scholarly.fill(pub)
        except Exception:
            filled = pub

        bib = filled.get("bib", {})
        title = bib.get("title", "")
        authors = bib.get("author", "")
        venue = bib.get("venue", bib.get("journal", bib.get("conference", "")))
        year = bib.get("pub_year", "")
        abstract = bib.get("abstract", "")
        citation_count = filled.get("num_citations", 0)

        # Get the URL - prefer pub_url, then eprint_url
        url = filled.get("pub_url", "")
        eprint = filled.get("eprint_url", "")

        # Check manual overrides
        if title in MANUAL_LINKS:
            url = MANUAL_LINKS[title]

        pubs.append({
            "title": title,
            "authors": authors,
            "venue": venue,
            "year": str(year),
            "url": url,
            "eprint_url": eprint,
            "citations": citation_count,
            "abstract": abstract[:200] if abstract else "",
        })

    # Sort by year descending, then by citations
    pubs.sort(key=lambda x: (x["year"], x["citations"]), reverse=True)
    return pubs


def format_authors(authors_str):
    """Format author string, bolding Gokmen."""
    # Handle both "and" separated and comma separated
    if not authors_str:
        return ""

    # Bold our name
    authors_str = re.sub(
        r"(MS Gokmen|M\.?S\.? Gokmen|Mahmut S(?:elman)? Gokmen|Gokmen,?\s*M\.?\s*S\.?)",
        r"<strong>\1</strong>",
        authors_str,
        flags=re.IGNORECASE,
    )
    return authors_str


def guess_tags(title, venue, abstract):
    """Generate relevant tags based on title/venue/abstract."""
    text = f"{title} {venue} {abstract}".lower()
    tags = []

    tag_keywords = {
        "Self-Supervised Learning": ["self-supervised", "dino", "ssl"],
        "Vision Transformer": ["vision transformer", "vit", "transformer"],
        "Medical Imaging": ["medical imag", "ct scan", "clinical", "radiology"],
        "Cardiac Imaging": ["coronary", "calcium", "cardiac", "heart", "cac"],
        "Histopathology": ["histopath", "pathology", "whole-slide", "wsi"],
        "Deep Learning": ["deep learning", "neural network", "cnn", "u-net"],
        "Knowledge Distillation": ["distillation", "distill"],
        "Computer Vision": ["computer vision", "image classif", "object detect"],
        "Report Generation": ["report generation", "radiology report"],
        "NLP": ["language model", "llm", "nlp", "text"],
        "Neuropathology": ["neuropath", "brain"],
        "Framework": ["framework", "platform", "system"],
        "Image Denoising": ["despeckl", "denois", "noise removal"],
        "Defect Detection": ["defect", "quality control", "lamella"],
        "Time Series": ["time series", "ecg", "heartbeat", "arrhythmia"],
    }

    for tag, keywords in tag_keywords.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)

    return tags[:3]  # Max 3 tags per paper


def detect_link_type(url):
    """Detect if link is DOI, arXiv, preprint, etc."""
    if not url:
        return None, None
    if "arxiv.org" in url:
        return "arXiv", url
    if "doi.org" in url or "springer.com" in url or "nature.com" in url:
        return "DOI", url
    if "researchsquare.com" in url:
        return "Preprint", url
    if "pubmed" in url:
        return "PubMed", url
    return "Link", url


def generate_pub_html(pub):
    """Generate HTML for a single publication."""
    title = pub["title"]
    authors = format_authors(pub["authors"])
    venue = pub["venue"]
    year = pub["year"]
    url = pub["url"]
    eprint = pub.get("eprint_url", "")
    tags = guess_tags(title, venue, pub.get("abstract", ""))

    # Title with link
    if url:
        title_html = f'<a href="{url}" target="_blank">{title}</a>'
    elif eprint:
        title_html = f'<a href="{eprint}" target="_blank">{title}</a>'
    else:
        title_html = title

    # Venue string
    venue_str = f"{venue}, {year}" if venue and year else venue or year

    # Tags HTML
    tags_html = "\n".join(
        f'            <span class="pub-tag">{tag}</span>' for tag in tags
    )

    # Links
    links = []
    link_type, link_url = detect_link_type(url)
    if link_type:
        links.append(f'<a class="pub-link" href="{link_url}" target="_blank">{link_type}</a>')

    if eprint and eprint != url:
        ep_type, ep_url = detect_link_type(eprint)
        if ep_type:
            links.append(f'<a class="pub-link" href="{ep_url}" target="_blank">{ep_type}</a>')

    links_html = "\n".join(f"            {l}" for l in links)

    return f"""        <div class="pub-item">
          <div class="pub-title">{title_html}</div>
          <div class="pub-authors">{authors}</div>
          <div class="pub-venue">{venue_str}</div>
          <div class="pub-tags">
{tags_html}
          </div>
          <div class="pub-links">
{links_html}
          </div>
        </div>"""


def update_index_html(pubs):
    """Replace the publications section in index.html."""
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # Generate all publication HTML
    pubs_html = "\n\n".join(generate_pub_html(pub) for pub in pubs)

    # Replace content between publication markers
    pattern = r'(<!-- PUBLICATIONS-START -->)(.*?)(<!-- PUBLICATIONS-END -->)'
    replacement = f"\\1\n{pubs_html}\n      \\3"

    new_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    if new_html == html and "PUBLICATIONS-START" not in html:
        print("WARNING: Publication markers not found in index.html.")
        print("Please add <!-- PUBLICATIONS-START --> and <!-- PUBLICATIONS-END --> markers.")
        return False

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(new_html)

    return True


def save_pubs_json(pubs):
    """Save publications to JSON for caching/debugging."""
    with open(PUBS_JSON, "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)


def main():
    print(f"Fetching publications for Scholar ID: {SCHOLAR_ID}")
    pubs = fetch_publications()
    print(f"Found {len(pubs)} publications")

    for pub in pubs:
        print(f"  - [{pub['year']}] {pub['title']}")

    save_pubs_json(pubs)
    print(f"Saved to {PUBS_JSON}")

    if update_index_html(pubs):
        print("Updated index.html successfully!")
    else:
        print("Failed to update index.html")


if __name__ == "__main__":
    main()
