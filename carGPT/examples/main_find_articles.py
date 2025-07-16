from datetime import datetime

from bs4 import BeautifulSoup

if __name__ == "__main__":
    with open("articles.html") as fp:
        soup = BeautifulSoup(fp, "lxml")

    today = datetime.now().date()

    next_page_link = soup.find(
        "button", class_="Pagination-link js-veza-stranica"
    )

    print(next_page_link)

    article_links = []

    for idx, ul in enumerate(soup.find_all("ul", class_="EntityList-items")):
        if idx == 2:
            for li in ul.find_all("li", recursive=False):
                try:
                    article_link = li.article.h3.a["href"]
                    date = li.find(
                        "div", class_="entity-pub-date"
                    ).time.contents[0]
                    date = datetime.strptime(date, "%d.%m.%Y.")

                    if date.date() != today:
                        break
                    article_links.append(article_link)
                except Exception:
                    continue
            break
