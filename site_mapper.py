#¡/usr/bin/env python3

import asyncio
import html.parser
import sys
import argparse

import site_graph
import request_queue
import logging

logger = logging.getLogger(__name__)

class SiteMapper(request_queue.RequestQueue.ResponseHandler):
    """Crawl sites asynchronously using asyncio and aiohttp"""
    def __init__(self, base_url: str):
        self.base_url = site_graph.URL(base_url)
        self.site_graph = site_graph.SiteGraph(self.base_url.host)
        self.request_queue = request_queue.RequestQueue(self)
    
    class LinkExtractor(html.parser.HTMLParser):
        "Extract the links from HTML pages"
        def __init__(self, url):
            super().__init__()  
            self.url = url
            self.links = set()

        def handle_starttag(self, tag, attrs):
            self._extract_links(tag, attrs)
            return super().handle_starttag(tag, attrs)

        def handle_startendtag(self, tag, attrs):
            self._extract_links(tag, attrs)
            return super().handle_startendtag(tag, attrs)

        def _extract_links(self, tag, attrs):
            if tag.lower() in { "link", "a" }:
                for name, value in attrs:
                    if name.lower() == "href" and value is not None:
                        link_url = site_graph.URL(value).with_fragment(None)
                        if self.is_potential_html(link_url):
                            if link_url.is_absolute():
                                abs_url = link_url
                            elif link_url.path.startswith("/"):
                                abs_url = self.url.with_path(link_url.path)
                            else:
                                abs_url = self.url / str(link_url)
                            self.links.add(abs_url)

        @staticmethod
        def is_potential_html(url: site_graph.URL):
            name = url.name.lower()
            return not ("." in name) or any(map(name.endswith, (".html", ".xhtml", ".html")))     


    async def crawl(self):
        await self.request_queue.load_robots_file(self.base_url)
        self.robots_file = self.request_queue.robots_file
        self.request_queue.enqueue(self.base_url)
        await self.request_queue.run()
        return

    def on_response(self, url_requested: site_graph.URL, url_served: site_graph.URL, status: int, text: str) -> None:
        if text is not None:
            lx = self.LinkExtractor(url_served)
            lx.feed(text)
            urls_referred = lx.links
        else:
            urls_referred = set()
        
        internal_links = self.site_graph.add_page(url_requested, urls_referred).internal_pages_referred
        if url_served != url_requested:
            self.site_graph.add_page(url_served, urls_referred)
        for url in internal_links:
            if self.robots_file is not None and not self.robots_file.can_fetch("*", str(url)):
                continue
            if self.site_graph.has_page(url):
                continue

            self.request_queue.enqueue(url)

class PrintingSiteMapper(SiteMapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.out_file = sys.stdout

    def on_response(self, url_requested: site_graph.URL, url_served: site_graph.URL, status: int, text: str) -> None:
        print(url_served, file = self.out_file)
        super().on_response(url_requested, url_served, status, text)
        

if __name__ == "__main__":
    def parse_args():
        parser = argparse.ArgumentParser(description = "Crawler that prints all the URLs in a site that can be reached from a starting point")
        parser.add_argument("site", type=str, help="The URL from which to start the crawl")
        parser.add_argument("-o", "--out", type=str, help="")
        return parser.parse_args()
        
    def main():
        args = parse_args()
        mapper = PrintingSiteMapper(args.site)
        if args.out is not None:
            mapper.out_file = open(args.out, "wt")
        asyncio.run(mapper.crawl())

    main()
