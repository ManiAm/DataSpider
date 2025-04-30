#!/usr/bin/env python3

# Author: Mani Amoozadeh
# Email: mani.amoozadeh2@gmail.com

import requests
import datetime
import redis
from celery import Celery
from elasticsearch import Elasticsearch
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

app = Celery(
    "scraper",
    broker="redis://redis_db_spider:6379/0",
    backend="redis://redis_db_spider:6379/0"
)

es = Elasticsearch("http://elasticsearch:9200")

rds = redis.Redis(host="redis_db_spider", port=6379, db=1)


@app.task
def scrape_url(url, depth):

    try:
        if not rds.sadd("visited_urls", url):
            return {"status": "skipped", "url": url}

        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except Exception as e:
        return {"status": "error", "url": url, "message": str(e)}

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        plain_text = soup.get_text()
        full_html = str(soup)
    except Exception as e:
        return {"status": "error", "url": url, "message": f"HTML parse failed: {str(e)}"}

    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
    except Exception as e:
        return {"status": "error", "url": url, "message": f"URL parse failed: {str(e)}"}

    try:
        doc = {
            "url": url,
            "domain": domain,
            "title": soup.title.string if soup.title else "",
            "content": plain_text,
            "html": full_html,
            "timestamp": datetime.datetime.utcnow()
        }
        es.index(index="webpages", document=doc)
    except Exception as e:
        return {"status": "error", "url": url, "message": f"Elasticsearch error: {str(e)}"}

    # Extract and queue child URLs
    if depth > 1:
        for child_url in get_page_links_internal(soup, url, domain):
            scrape_url.delay(child_url, depth - 1)

    return {"status": "success", "url": url, "depth": depth}


def get_page_links_internal(soup, base_url, base_domain):

    links = set()

    for href in get_page_links(soup):

        full_url = urljoin(base_url, href)
        domain = urlparse(full_url).netloc

        if domain != base_domain:
            continue

        # Strip fragments
        full_url = full_url.split('#')[0]

        links.add(full_url)

    return list(links)


def get_page_links(soup):

    links = set()

    for tag in soup.find_all("a", href=True):

        href = tag['href'].strip()

        # Ignore empty or fragment-only hrefs
        if not href or href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue

        links.add(href)

    return list(links)
