#!/usr/bin/env python3

# Author: Mani Amoozadeh
# Email: mani.amoozadeh2@gmail.com

import requests
import datetime
import redis
import uuid
from celery import Celery, chord, group
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
def scrape_url(url, depth, batch_id):

    key = f"active_crawl:{batch_id}"

    try:
        if not rds.sadd(key, url):
            return {
                "status": "skipped",
                "url": url,
                "depth": depth,
                "batch_id": batch_id
            }

        response = requests.get(url, timeout=5)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        plain_text = soup.get_text()
        full_html = str(soup)

        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        doc = {
            "url": url,
            "domain": domain,
            "title": soup.title.string if soup.title else "",
            "content": plain_text,
            "html": full_html,
            "timestamp": datetime.datetime.utcnow()
        }

        es.index(index="webpages", document=doc)

        links = get_page_links_internal(soup, url, domain)
        return {
            "status": "success",
            "url": url,
            "depth": depth,
            "batch_id": batch_id,
            "links": links
        }

    except Exception as e:
        print("exception in scrape_url", flush=True)
        return {
            "status": "error",
            "url": url,
            "depth": depth,
            "batch_id": batch_id,
            "message": str(e)
        }


@app.task
def process_scraped_links(results, batch_id):

    if not results:
        return crawl_finished.delay([], batch_id)

    next_tasks = []
    for result in results:
        if result.get("status") == "success" and result["depth"] > 1:
            next_depth = result["depth"] - 1
            for link in result.get("links", []):
                next_tasks.append(scrape_url.s(link, next_depth, batch_id))

    if next_tasks:
        chord_s = chord(group(next_tasks), process_scraped_links.s(batch_id))
        return chord_s.apply_async()

    return crawl_finished.delay([], batch_id)


@app.task
def crawl_finished(results, batch_id):

    key = f"active_crawl:{batch_id}"
    print(f"Crawl completed. Cleaned up Redis set '{key}'.", flush=True)
    rds.delete(key)

    return {
        "status": "finished",
        "batch_id": batch_id,
        "message": "All scraping tasks completed."
    }


@app.task
def start_crawl(url, depth):

    batch_id = str(uuid.uuid4())
    print(f"Starting new crawl for '{url}' with depth {depth} and batch_id: '{batch_id}'", flush=True)

    scrape_url_sig = scrape_url.s(url, depth, batch_id)
    process_scraped_links_sig = process_scraped_links.s(batch_id)

    chord_s = chord([scrape_url_sig], process_scraped_links_sig)
    async_result = chord_s.apply_async()

    return {
        "batch_id": batch_id,
        "chord_id": async_result.id,        # ID of the callback task
        "group_id": async_result.parent.id  # ID of the group of header tasks
    }


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
