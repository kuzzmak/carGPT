import scrapy


class NjuskaloSpider(scrapy.Spider):
    name = "njuskalo"
    start_urls = [
        'https://www.njuskalo.hr/auti',
    ]

    def parse(self, response):
        articles = response.xpath('//*[@id="form_browse_detailed_search"]/div/div[1]/div[6]/div[6]/ul')
        print('articles:', articles)
        # for car in response.xpath('//*[@id="form_browse_detailed_search"]/div/div[1]/div[6]/div[6]'):
        #     print(car)
        #     print('-------------------')
        #     yield car
        # for car in response.css('div.EntityList-item--Regular'):
        #     yield {
        #         'title': car.css('div.EntityList-item--Regular-title a::text').get(),
        #         'price': car.css('div.EntityList-item--Regular-pricing-price span::text').get(),
        #         'year': car.css('div.EntityList-item--Regular-title a::text').get().split()[-1],
        #         'link': car.css('div.EntityList-item--Regular-title a::attr(href)').get(),
        #     }

        # next_page = response.css('a.Button--Pagination::attr(href)').get()
        # if next_page is not None:
        #     yield response.follow(next_page, self.parse)