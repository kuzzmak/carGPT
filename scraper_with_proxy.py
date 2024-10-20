import os
import re
import sys
sys.path.append('/home/tonkec/Documents/carGPT/carGPT/scraper')
os.environ['SCRAPY_SETTINGS_MODULE'] = 'carGPT.scraper.scraper.settings'

from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging

import stem.process

# from carGPT.scraper.scraper.settings import settings
from carGPT.scraper.scraper.spiders.njuskalo_spider import NjuskaloSpider


if __name__ == '__main__':
    SOCKS_PORT = 9050
    TOR_PATH = os.path.normpath(
        "/home/tonkec/Downloads/tor-browser/Browser/TorBrowser/Tor/tor")
    tor_process = stem.process.launch_tor_with_config(
        config={
            'SocksPort': str(SOCKS_PORT),
        },
        init_msg_handler=lambda line: print(line) if re.search(
            'Bootstrapped', line) else False,
        tor_cmd=TOR_PATH
    )

    settings = get_project_settings()
    process = CrawlerProcess(settings)

    process.crawl(NjuskaloSpider)
    process.start()

    tor_process.kill()
