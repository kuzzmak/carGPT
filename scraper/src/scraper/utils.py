import re
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from shared.database import AdColumns
from shared.translations import TRANSLATIONS

from scraper.logger import logger


def transform_data(data):
    """Transform and clean extracted data"""

    def year_transform(year: str):
        return int(year.split(".")[0]) if "." in year else int(year)

    def boolean_transform(value: str):
        return value.lower() == "da"

    def price_transform(price: str):
        price = price.replace(".", "")
        price = price.replace(",", ".")
        price = price.replace("€", "").strip()
        try:
            return float(price)
        except ValueError:
            return price

    transformations = {
        AdColumns.MANUFACTURE_YEAR: lambda x: year_transform(x),
        AdColumns.MODEL_YEAR: lambda x: year_transform(x),
        AdColumns.MILEAGE: lambda x: int(x.split()[0].replace(".", "")),
        AdColumns.POWER: lambda x: int(x.split()[0]),
        AdColumns.SERVICE_BOOK: lambda x: boolean_transform(x),
        AdColumns.FUEL_CONSUMPTION: lambda x: float(
            x.split()[0].replace(",", ".")
        ),
        AdColumns.AVERAGE_CO2_EMISSION: lambda x: float(
            x.split()[0].replace(",", ".")
        ),
        AdColumns.OWNER: lambda x: int(x.split()[0])
        if x.split()[0].isdigit()
        else x,
        AdColumns.DISPLACEMENT: lambda x: int(
            x.replace(".", "").replace(" cm3", "")
        ),
        AdColumns.IN_TRAFFIC_SINCE: lambda x: year_transform(x),
        AdColumns.FIRST_REGISTRATION_IN_CROATIA: lambda x: year_transform(x),
        AdColumns.GARAGED: lambda x: boolean_transform(x),
        AdColumns.VIDEO_CALL_VIEWING: lambda x: boolean_transform(x),
        AdColumns.GAS: lambda x: boolean_transform(x),
        AdColumns.PRICE: lambda x: price_transform(x),
    }

    transformed_data = {}
    for key, value in data.items():
        if key in transformations:
            try:
                transformed_data[key] = transformations[key](value)
            except Exception as e:
                logger.error(f"Error transforming {key}: {e}")
                transformed_data[key] = value  # fallback to original value
        else:
            transformed_data[key] = value  # no transformation needed

    return transformed_data


def get_ad_details(
    left_column: list[WebElement], right_column: list[WebElement]
) -> dict[str, str]:
    ad_details = {}
    for prop_name, prop_value in zip(left_column, right_column, strict=True):
        prop_name = prop_name.find_element(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-textWrapContainer"
        ).text
        prop_value = prop_value.find_element(
            By.CLASS_NAME, "ClassifiedDetailBasicDetails-textWrapContainer"
        ).text
        try:
            ad_details[TRANSLATIONS[prop_name]] = prop_value
        except KeyError:
            logger.warning(f"No key for: {prop_name} - value: {prop_value}")

    return ad_details


def round_up_to_next_hour(dt: datetime) -> datetime:
    """Rounds a datetime up to the next full hour."""
    if dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return dt
    return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def parse_date_string(
    date_str: str, base_time: datetime | None = None
) -> datetime | None:
    """
    Parses strings like '26 dana i 21 sat' into a datetime object rounded up to the next full hour.
    Returns None for 'do prodaje'.
    """
    if base_time is None:
        base_time = datetime.now()

    date_str = date_str.strip().lower()

    if date_str == "do prodaje":
        return None

    # Match e.g. '13 dana i 8 sati', '0 dana i 2 sata'
    pattern = r"(\d+)\s*dana?(?:\s*i\s*(\d+)\s*sat[ai]?)?"

    match = re.match(pattern, date_str)

    if not match:
        raise ValueError(f"Unrecognized date format: '{date_str}'")

    days = int(match.group(1))
    hours = int(match.group(2)) if match.group(2) else 0

    result = base_time + timedelta(days=days, hours=hours)
    return round_up_to_next_hour(result)


def get_ad_links(page_ads: list[WebElement]) -> list[str]:
    """Extract ad links from page ads"""
    ad_links = []
    for ad in page_ads:
        try:
            ad_class = ad.get_attribute("class")
            if (
                ad_class is not None
                and "EntityList-bannerContainer" in ad_class
            ):
                logger.debug("Skipping banner container")
                continue
            article = ad.find_element(By.TAG_NAME, "article")
            article_title = article.find_element(By.CLASS_NAME, "entity-title")
            article_link = article_title.find_element(By.TAG_NAME, "a")
            article_link_url = article_link.get_attribute("href")
            ad_links.append(article_link_url)
        except Exception as e:
            logger.error(f"Error extracting ad link: {e}")
    return ad_links
