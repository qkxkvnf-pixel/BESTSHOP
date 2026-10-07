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

PAT = re.compile(r"^(https://www\.lge\.co\.kr)?/[a-z\-]+/[a-z0-9\-]+$")

def cards(s, loose):
    if not loose:
        return s.find_all("li")
    out, seen = [], set()
    for a in s.find_all("a", href=True):
        if not PAT.match(a["href"]):
            continue
        n = a
        for _ in range(8):
            q = n.parent
            if q is None or len({x["href"] for x in q.find_all("a", href=True) if PAT.match(x["href"])}) > 1:
                break
            n = q
        if id(n) not in seen:
            seen.add(id(n)); out.append(n)
    return out

def parse(html, only_flag=False, tag="타임딜", loose=False):
    s, out = BeautifulSoup(html, "html.parser"), {}
    for li in cards(s, loose):
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
        c = SLUG.get(slug) or ("기타" if loose else (re.sub(r"\d+개$", "", h.get_text(strip=True)) if h else slug))
        out[url] = dict(name=name, url=url, img=(B + img if img.startswith("/") else img), price=price,
                        cat=c, tags=[tag] + (["닷컴ONLY"] if only and tag != "닷컴ONLY" else []))
    return out

URLRE = re.compile(r"^(?:https://www\.lge\.co\.kr)?(/[a-z0-9\-]+/[A-Za-z0-9\-_]+)/?(?:\?.*)?$")
BAD = ("subscri", "month", "rental", "care", "install", "point", "mlb")

def flat(o, out=None):
    out = {} if out is None else out
    for k, v in o.items():
        if isinstance(v, dict): flat(v, out)
        elif isinstance(v, (str, int, float)): out.setdefault(k, v)
    return out

def find_products(o, res):
    if isinstance(o, dict):
        f = flat(o)
        url = next((URLRE.match(v).group(1) for v in f.values() if isinstance(v, str) and URLRE.match(v) and not re.search(r"\.(jpg|png|webp|svg)", v)), None)
        prices = []
        for k, v in f.items():
            if "price" in k.lower() and not any(w in k.lower() for w in BAD):
                try: n = int(float(str(v).replace(",", "")))
                except Exception: continue
                if n >= 10000: prices.append(n)
        if url and prices and B + url not in res:
            img = next((v for v in f.values() if isinstance(v, str) and re.search(r"\.(jpg|jpeg|png|webp)", v) and ("/kr/" in v or v.startswith("http"))), "")
            names = [v for k, v in f.items() if isinstance(v, str) and ("name" in k.lower() or "title" in k.lower()) and len(v) >= 5 and not URLRE.match(v)]
            name = max(names, key=len) if names else url
            img = (B + img if img.startswith("/") else img)
            res[B + url] = dict(name=name, url=B + url, img=img, price=min(prices),
                                cat=SLUG.get(url.split("/")[1], "기타"), tags=["닷컴ONLY"])
        for v in o.values(): find_products(v, res)
    elif isinstance(o, list):
        for v in o: find_products(v, res)

def search_only():
    from playwright.sync_api import sync_playwright
    res, raw, pages = {}, "", 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"])
        kw = urllib.parse.quote("닷컴ONLY")
        pg.goto(B + "/sch?keyword=" + kw + "&tab=all", wait_until="networkidle", timeout=90000)
        H = {"Origin": B, "Referer": B + "/", "Accept": "application/json"}
        for page in range(1, 80):
            u = "https://apiv2.lge.co.kr/searchsvc/ajax/v2/search/product?keyword=%s&attrs=&sort=BEST&page=%d&size=100" % (kw, page)
            r = pg.context.request.get(u, headers=H, timeout=60000)
            txt = r.text()
            if page == 1: raw = "HTTP %s " % r.status + txt[:1500]
            before = len(res)
            try: find_products(json.loads(txt), res)
            except Exception: break
            pages = page
            if len(res) == before: break
        b.close()
    status["debug"] = {"count": "수집 %d, 페이지 %d" % (len(res), pages), "raw": raw if not res else raw[:300]}
    if not res:
        status["errors"].append("닷컴ONLY 0건 - 진단 저장됨")
    return res

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
for v in list(items.values())[:200]:
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
