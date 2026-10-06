import re, json, datetime, urllib.request, urllib.parse
from bs4 import BeautifulSoup
B = "https://www.lge.co.kr"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"}
TIMEDEAL = B + "/benefits/exhibitions/detail-PE00385001"
SLUG = {"tvs": "TV", "refrigerators": "냉장고", "kimchi-refrigerators": "김치냉장고", "convertible-refrigerators": "컨버터블 패키지",
        "washing-machines": "세탁기", "wash-tower": "워시타워", "wash-combo": "워시콤보", "dryers": "건조기",
        "air-conditioners": "에어컨", "air-purifier": "공기청정기", "vacuum-cleaners": "청소기", "notebook": "노트북",
        "monitors": "모니터", "water-purifiers": "정수기", "lg-styler": "스타일러", "dishwashers": "식기세척기",
        "electric-ranges": "전기레인지", "humidifiers": "가습기", "dehumidifiers": "제습기", "massage-chairs": "안마의자",
        "microwaves-and-ovens": "광파오븐/전자레인지", "home-audio": "오디오", "projectors": "프로젝터",
        "stan-by-me": "스탠바이미", "winecellar": "와인셀러"}

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40).read().decode("utf-8", "ignore")

def num(p, t):
    m = re.search(p + r"\s*([\d,]{4,})\s*원", t)
    return int(m.group(1).replace(",", "")) if m else None

def parse(html, only_flag=False, tag="타임딜", loose=False):
    s, out = BeautifulSoup(html, "html.parser"), {}
    for li in s.find_all("li"):
        t = li.get_text(" ", strip=True)
        if ("판매가" not in t and not loose) or "SOLD OUT" in t or "일시품절" in t:
            continue
        a = next((x for x in li.find_all("a", href=True)
                  if re.match(r"^(https://www\.lge\.co\.kr)?/[a-z\-]+/[a-z0-9\-]+$", x["href"])), None)
        if not a:
            continue
        only = ("닷컴" in t and "ONLY" in t) or any("닷컴" in (i.get("alt") or "") for i in li.find_all("img"))
        if only_flag and not only:
            continue
        url = a["href"] if a["href"].startswith("http") else B + a["href"]
        price = num("최대혜택가", t) or num("할인 후 판매가", t) or num("판매가", t)
        if not price and loose:
            m = re.search(r"([\d,]{5,})\s*원", t)
            price = int(m.group(1).replace(",", "")) if m else None
        if not price:
            continue
        img = next((i.get("src") or i.get("data-src") for i in li.find_all("img")
                    if "/kr/images/" in (i.get("src") or i.get("data-src") or "")), "")
        name = re.sub(r"닷컴\s*ONLY", "", a.get_text(" ", strip=True)).strip()
        if not name:
            name = re.sub(r"닷컴\s*ONLY", "", next((i.get("alt", "") for i in li.find_all("img")), "")).strip()
        h = li.find_previous("h3")
        slug = url.split("/")[3]
        c = SLUG.get(slug) or (re.sub(r"\d+개$", "", h.get_text(strip=True)) if h and not loose else slug)
        out[url] = dict(name=name, url=url, img=(B + img if img.startswith("/") else img), price=price,
                        cat=c, tags=[tag] + (["닷컴ONLY"] if only and tag != "닷컴ONLY" else []))
    return out

def search_only():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"], viewport={"width": 430, "height": 900})
        pg.goto(B + "/sch?keyword=" + urllib.parse.quote("닷컴ONLY") + "&tab=all", wait_until="networkidle", timeout=90000)
        try:
            pg.get_by_text(re.compile(r"^제품")).first.click(timeout=4000); pg.wait_for_timeout(2000)
        except Exception:
            pass
        last, same = -1, 0
        for _ in range(150):
            pg.mouse.wheel(0, 8000); pg.wait_for_timeout(800)
            try: pg.get_by_role("button", name=re.compile("더보기")).first.click(timeout=600)
            except Exception: pass
            n = pg.locator("li:has(img)").count()
            same = same + 1 if n == last else 0
            last = n
            if same >= 4: break
        html = pg.content(); b.close()
    return parse(html, only_flag=True, tag="닷컴ONLY", loose=True)

items, status = {}, {"errors": []}
def merge(d):
    for u, v in d.items():
        if u in items:
            items[u]["tags"] = sorted(set(items[u]["tags"] + v["tags"]))
            items[u]["price"] = min(items[u]["price"], v["price"])
            items[u]["img"] = items[u]["img"] or v["img"]
        else:
            items[u] = v

try:
    d = parse(get(TIMEDEAL)); status["timedeal"] = len(d); merge(d)
except Exception as e:
    status["errors"].append("타임딜: %s" % e)
try:
    d = search_only(); status["only"] = len(d); merge(d)
except Exception as e:
    status["only"] = 0; status["errors"].append("닷컴ONLY 검색: %s" % e)
for v in list(items.values())[:80]:
    if not v["img"]:
        try:
            m = re.search(r'property="og:image"\s+content="([^"]+)"', get(v["url"])); v["img"] = m.group(1) if m else ""
        except Exception: pass
if items:
    kst = datetime.timezone(datetime.timedelta(hours=9))
    json.dump({"updated": datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "status": status,
               "items": sorted(items.values(), key=lambda x: (x["cat"], x["price"]))},
              open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    raise SystemExit("수집 0건 - 기존 데이터 유지: %s" % status)
