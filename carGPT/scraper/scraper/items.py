# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ScraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class NjuskaloCarItem(scrapy.Item):
    url = scrapy.Field()
    title = scrapy.Field()
    price = scrapy.Field()
    location = scrapy.Field()
    make = scrapy.Field()
    model = scrapy.Field()
    type = scrapy.Field()
    chassis_number = scrapy.Field()
    manufacture_year = scrapy.Field()
    model_year = scrapy.Field()
    mileage = scrapy.Field()
    engine = scrapy.Field()
    power = scrapy.Field()
    displacement = scrapy.Field()
    transmission = scrapy.Field()
    condition = scrapy.Field()
    owner = scrapy.Field()
    service_book = scrapy.Field()
    garaged = scrapy.Field()
    in_traffic_since = scrapy.Field()
    first_registration_in_croatia = scrapy.Field()
    registered_until = scrapy.Field()
    fuel_consumption = scrapy.Field()
    eco_category = scrapy.Field()
    number_of_gears = scrapy.Field()
    number_of_seats = scrapy.Field()
    number_of_doors = scrapy.Field()
    warranty = scrapy.Field()
    average_CO2_emission = scrapy.Field()
    video_call_viewing = scrapy.Field()
    gas = scrapy.Field()
    auto_warranty = scrapy.Field()
    chassis_type = scrapy.Field()
    drive_type = scrapy.Field()
    color = scrapy.Field()
    metalic_color = scrapy.Field()
    suspension = scrapy.Field()
    tire_size = scrapy.Field()
    internal_code = scrapy.Field()
