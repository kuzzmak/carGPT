from datetime import datetime, timedelta
from typing import Iterable

from bs4 import BeautifulSoup
import scrapy
from scrapy.http import Request

from carGPT.scraper.scraper.items import NjuskaloCarItem
from carGPT.scraper.scraper.translations import TRANSLATIONS


class NjuskaloSpider(scrapy.Spider):
    name = "njuskalo"
    url_template = "https://www.njuskalo.hr/auti?page={page}"
    curr_page = 1

    def start_requests(self) -> Iterable[Request]:
        yield Request(
            url=self.url_template.format(page=self.curr_page),
        )

    def parse(self, response):
        self.logger.info(f"Parsing page: {self.curr_page}")

        soup = BeautifulSoup(response.text, "lxml")

        next_page_link = soup.find_all(
            "button", class_="Pagination-link js-veza-stranica")
        if not next_page_link:
            self.logger.info("No next page found")
            return

        article_links = []
        today = datetime.now().date()
        self.logger.info(f"Searching for articles for a date: {today}")
        prev_day_date = today - timedelta(days=1)
        yesterday = False

        for idx, ul in enumerate(soup.find_all("ul", class_="EntityList-items")):
            # on first page relevant car articles section is third while using find and first on other pages
            if (self.curr_page == 1 and idx == 2) or (self.curr_page > 1 and idx == 0):
                for li in ul.find_all("li", recursive=False):
                    try:
                        article_link = li.article.h3.a["href"]
                        self.logger.info(f"Found article link: {article_link}")
                        date = li.find(
                            "div", class_="entity-pub-date").time.contents[0]
                        date = datetime.strptime(date, "%d.%m.%Y.")
                        self.logger.info(f"Article date: {date}")
                        # if the date is from yesterday, stop the search
                        if date.date() == prev_day_date:
                            self.logger.info(
                                "Yesterday's articles found, stopping search")
                            yesterday = True
                            break
                        article_links.append(article_link)
                    except Exception:
                        continue
                break

        self.curr_page = int(next_page_link[-1]["data-page"])

        for link in article_links:
            yield response.follow(link, self.parse_article)

        # yield response.follow(article_links[0], self.parse_article)

        if not yesterday:
            self.logger.info(f"Going to next page: {self.curr_page}")
            yield response.follow(self.url_template.format(page=self.curr_page), callback=self.parse)

        # with open('articles.html', 'w') as f:
        #     f.write(response.text)

    def parse_article(self, response):
        self.logger.info(f"Parsing article: {response.url}")

        soup = BeautifulSoup(response.text, "lxml")

        def clean_text(text):
            return text.replace("\n", "").replace("\\xa", "").strip()

        additional_info = {}
        additional_info_html = soup.find_all(
            "section", class_="ClassifiedDetailPropertyGroups-group")
        for info_html in additional_info_html:

            if info_html.h3.contents[0] != "Dodatni podaci":
                continue

            for li in info_html.div.ul.find_all("li"):
                section = li.contents[0]

                # tire size needs special handling because it can have multiple values
                if "Veličina guma" in section:
                    section_name = "Veličina guma"
                    # Veličina guma: Širina: 215, Visina: 60, Promjer: 17
                    if "Visina" in section:
                        width, aspect_ratio, diameter = section.split(", ")
                        width = width.split(": ")[-1]
                        aspect_ratio = aspect_ratio.split(": ")[1]
                        diameter = diameter.split(": ")[1]
                        section_val = f"{width}/{aspect_ratio}R{diameter}"
                    # Veličina guma: Promjer: 18
                    else:
                        diameter = section.split(": ")[-1]
                else:
                    section_name, section_val = section.split(": ")

                section_name = clean_text(section_name)
                section_val = clean_text(section_val)
                key_translated = TRANSLATIONS.get(section_name, None)
                if key_translated is None:
                    self.logger.error(
                        f"Found key: \"{section_name}\" which is not translated.")
                    continue
                additional_info[key_translated] = section_val

            break

        info_html = soup.find(
            "dl", class_="ClassifiedDetailBasicDetails-list cf")
        dt_all = info_html.find_all("dt")
        dd_all = info_html.find_all("dd")
        article_title = soup.find(
            "h1", class_="ClassifiedDetailSummary-title").contents[0]
        price = soup.find(
            "dd", class_="ClassifiedDetailSummary-priceDomestic").contents[0]
        price = clean_text(price)
        item = NjuskaloCarItem()
        item["url"] = response.url
        item["title"] = article_title
        item["price"] = price

        item.update(additional_info)

        for dt, dd in zip(dt_all, dd_all):
            key = dt.span.contents[0]
            translated_key = TRANSLATIONS.get(key, None)
            if translated_key is None:
                self.logger.error(
                    f"Found key: \"{key}\" which is not translated.")
                continue

            val = dd.span.contents[0]
            item[translated_key] = val

        yield item
