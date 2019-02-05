import collections
import datetime
import typing
from yarl import URL

class SiteGraph:
    PageLinks = collections.namedtuple("PageLinks", ["internal_pages_referred", "external_pages_referred", "time_crawled"])

    def __init__(self, net_location: str):
        self.net_location = net_location
        self.pages = collections.OrderedDict()

    def add_page(self, url: URL, pages_referred: typing.Iterable[URL]) -> PageLinks:
        """Add a page to the graph. Add and return information about the links in it + a timestamp"""
        internal = set()
        external = set()
        for page in pages_referred:
            if page.host == self.net_location:
                internal.add(page)
            else:
                external.add(page)
            
        links = self.PageLinks(frozenset(internal), frozenset(external), datetime.datetime.now())
        self.pages[url] = links
        return links

    def has_page(self, url: URL) -> bool:
        return url in self.pages

    @property
    def root_url(self) -> URL:
        return self.pages[0][0]
