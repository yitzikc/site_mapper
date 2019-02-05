import asyncio
import http
import aiohttp.client
import urllib.robotparser
import datetime
import collections
import logging
import abc

logger = logging.getLogger(__name__)

import site_graph

class RequestQueue:
    """A queue of pending HTTP requests, that maintains a minimum interval between outgoing requests
    It supports determining the rate by """

    RequestContext = collections.namedtuple("RequestContext", ["time_enqueued", "times_retried"])

    class ResponseHandler(metaclass = abc.ABCMeta):
        """An abstract base class for handles of HTTP responses"""
        @abc.abstractmethod
        def on_response(self, url_requested: site_graph.URL, url_served: site_graph.URL, status: int, text: str) -> None:
            """Abstract method representing an HTTP response. Note that the URL served could differ from the one requested, due to reedirects"""
            pass

    def __init__(self, handler: ResponseHandler):
        self.handler = handler
        self.seconds_interval = 0.5 
        self.queue = collections.OrderedDict()
        self.robots_file = None

        # TODO: separate this from the class to make it more reusable
        self.req_headers = { "Accept": "text/html,application/xhtml+xml;q=0.9" }

    def enqueue(self, url: site_graph.URL):
        if url in self.queue:
            return
        now = asyncio.get_running_loop().time()
        self.queue[url] = self.RequestContext(now, 0)
        
    async def load_robots_file(self, site_origin: site_graph.URL):
        """Load the configuration in the site's robots.txt. site_origin should give the site's top-level URL"""
        robots_url = site_origin.with_path("/robots.txt")
        async with aiohttp.client.ClientSession() as session:
            async with session.get(robots_url, headers = self.req_headers) as resp:
                if resp.status != http.HTTPStatus.OK.value:
                    if resp.status != http.HTTPStatus.NOT_FOUND.value:
                        logger.warning("Unexpected http status {} while trying to get robots.txt.".format(resp.status))
                    return

                content = await resp.text()
                rp = urllib.robotparser.RobotFileParser(str(robots_url))
                rp.parse(content.splitlines())

                crawl_delay = None
                try:
                    crawl_delay = rp.crawl_delay("*")
                except Exception as ex:
                    logger.warning("Failed to read crawl delay from robots.txt: {}.".format(ex))

                if crawl_delay:
                    self.seconds_interval = crawl_delay
                else:
                    rate = None
                    try:
                        rate = rp.request_rate("*")
                    except Exception as ex:
                        logger.warning("Failed to read request rate from robots.txt: {}.".format(ex))
                    if rate is not None:
                        self.seconds_interval = rate.seconds / rate.requests
                self.robots_file = rp

    async def run(self):
        # A session that will serve all the requests from this queue. Since we don't expect to make
        # more than 2 requests per second, this would likely suffice.
        async with aiohttp.client.ClientSession() as session:
            self.session = session
            loop = asyncio.get_running_loop()
            next_time_to_send = loop.time()
            while self.queue:
                now = loop.time()
                if now < next_time_to_send:
                    await asyncio.sleep(next_time_to_send - now)
                    now = loop.time()
                next_time_to_send = now + self.seconds_interval
                url, context = self.queue.popitem(last = False)
                await self._send_http_request(url, context)

        self.session = None
        return

    async def _send_http_request(self, url: site_graph.URL, request_context: RequestContext):
        async with self.session.get(url, headers = self.req_headers) as resp:
            if resp.status == http.HTTPStatus.OK.value:
                html = await resp.text()
                self.handler.on_response(url, resp.url, resp.status, html)
            elif resp.status ==  http.HTTPStatus.SERVICE_UNAVAILABLE.value:
                logger.warning("Request for {} failed temporarily with HTTP status {} and will be retried".format(url, resp.status))
                # TODO: Give up after a certain number of retries.
                self.queue[url] = self.RequestContext(asyncio.get_running_loop().time(), request_context.times_retried + 1)
                self.handler
            else:
                if resp.status != http.HTTPStatus.NOT_ACCEPTABLE.value:    # No HTML available for this URL
                    logger.error("Request for the URL {} gave unexpected status {}".format(url, resp.status))
                self.handler.on_response(url, resp.url, resp.status, None)

