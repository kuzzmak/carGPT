# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter

from carGPT.database.database import Database


class ScraperPipeline:
    def process_item(self, item, spider):
        return item


class DatabasePipeline:

    def open_spider(self, spider):
        db = Database()
        self.db = db.db
        
    def process_item(self, item, spider):
        keys = list(item.keys())
        keys_str = ', '.join(keys)
        vals = list(item.values())
        vals_str = ', '.join([f'"{val}"' for val in vals])
        insert_query = f'INSERT INTO articles ({keys_str}) VALUES ({vals_str})'
        self.db.run(insert_query)
        return item