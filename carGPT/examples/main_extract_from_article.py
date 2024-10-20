from bs4 import BeautifulSoup


if __name__ == '__main__':
    with open("data/audi_a4.html") as fp:
        soup = BeautifulSoup(fp, "lxml")

    info = soup.find("dl", class_="ClassifiedDetailBasicDetails-list cf")
    dt_all = info.find_all("dt")
    dd_all = info.find_all("dd")

    for dt, dd in zip(dt_all, dd_all):
        print(dt.span.contents, dd.span.contents)