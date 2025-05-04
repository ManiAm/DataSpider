#!/usr/bin/env python3

# Author: Mani Amoozadeh
# Email: mani.amoozadeh2@gmail.com

import re
import html
from elasticsearch import Elasticsearch
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from flask import Flask, render_template, request, abort

import grpc
import scraper_pb2
import scraper_pb2_grpc

app = Flask(__name__)

channel = grpc.insecure_channel("grpc_server:50051")
stub = scraper_pb2_grpc.ScraperServiceStub(channel)

es = Elasticsearch("http://elasticsearch:9200")


def prepare_html_for_srcdoc(raw_html, query, base_url):

    html_style = update_style(raw_html)
    highlighted_html = highlight_in_html(html_style, query)
    final_html = rewrite_relative_urls(highlighted_html, base_url)

    # Unescape entities and clean up formatting
    unescaped = html.unescape(final_html)
    clean = unescaped.replace("\n", "").replace('"', "'")

    return clean


def update_style(html_code):

    soup = BeautifulSoup(html_code, "html.parser")

    # Each iframe is a self-contained HTML document, with its own <head>, styles, and context.
    # The iframe cannot access the main CSS.

    style_tag = soup.new_tag("style")
    style_tag.string = """
    mark {
        background-color: yellow;
        color: black;
        font-weight: bold;
        padding: 0 2px;
    }
    """

    script_tag = soup.new_tag("script")
    script_tag.string = """
        document.addEventListener("DOMContentLoaded", function () {
            document.querySelectorAll("a").forEach(function (a) {
                a.addEventListener("click", function (e) {
                    e.preventDefault();
                });
            });
        });
    """

    if soup.head:
        soup.head.append(style_tag)
        soup.head.append(script_tag)
    else:
        head = soup.new_tag("head")
        head.append(style_tag)
        head.append(script_tag)
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)

    return str(soup)


def highlight_in_html(html_code, query):

    soup = BeautifulSoup(html_code, "html.parser")

    def highlight_text_nodes(el):

        for child in el.children:

            if child.name is None and isinstance(child, str):
                highlighted = re.sub(
                    f"({re.escape(query)})",
                    r"<mark>\1</mark>",
                    child,
                    flags=re.IGNORECASE
                )
                child.replace_with(highlighted)

            elif hasattr(child, "children"):
                highlight_text_nodes(child)

    highlight_text_nodes(soup)

    return str(soup)


def rewrite_relative_urls(html_code, base_url):

    soup = BeautifulSoup(html_code, "html.parser")

    base = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

    for tag in soup.find_all(["link", "script", "img", "a"]):

        attr = "href" if tag.name in ["link", "a"] else "src"

        if tag.has_attr(attr):

            if tag[attr].startswith("/"):
                tag[attr] = urljoin(base, tag[attr])

    return str(soup)


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "GET":
        return render_template("index.html")

    if request.method == "POST":

        if "submit" in request.form:

            url = request.form["url"]
            depth = int(request.form["depth"])
            depth = max(1, depth)
            response = stub.SubmitUrl(scraper_pb2.UrlRequest(url=url, depth=depth))
            job_id = response.job_id
            return render_template("index.html", job_id=job_id)

        elif "check" in request.form:

            job_id = request.form["job_id"]
            result = stub.CheckStatus(scraper_pb2.JobRequest(job_id=job_id))
            return render_template("index.html", job_id=job_id, status=result.status, content=result.content)

        elif "search" in request.form:

            query = request.form["search_query"]
            max_results = request.form["max_results"]

            match_whole_word = "match_whole_word" in request.form
            match_case = "match_case" in request.form
            use_reg_exp = "use_reg_exp" in request.form

            # curl -X POST http://localhost:9200/webpages/_search?pretty \
            #   -H "Content-Type: application/json" \
            #   -d '{
            #     "query": {
            #       "match": {
            #         "content": "world"
            #       }
            #     }
            #   }'

            body = {
                "query": {
                    "match": {
                        "content": query
                    }
                },
                "size": int(max_results)
            }

            if not es.indices.exists(index="webpages"):
                return render_template("index.html")

            results = es.search(index="webpages", body=body)

            results_count = results["hits"]["total"]["value"]
            hits = results["hits"]["hits"]

            search_results = []

            for r in hits:

                url = r["_source"]["url"]
                raw_html = r["_source"].get("html", "")
                timestamp = r["_source"].get("timestamp")

                processed_html = prepare_html_for_srcdoc(raw_html, query, url)

                search_results.append({
                    "url": url,
                    "html": processed_html,
                    "timestamp": timestamp
                })

            search_results.sort(key=lambda x: (x["url"], len(x["url"])))

            return render_template("index.html",
                                   results_count=results_count,
                                   search_results=search_results,
                                   search_query=query)

        else:

            abort(400, description="Unsupported form action.")

    abort(405)


if __name__ == "__main__":

    app.run(host="0.0.0.0", port=5000)
