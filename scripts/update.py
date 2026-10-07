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

def dd(t):
    r = {}
    m = re.search(r"D-(\d+|DAY)", t)
    if m: r["dday"] = 0 if m.group(1) == "DAY" else int(m.group(1))
    m = re.search(r"(\d+)\s*개 남음", t)
    if m: r["stock"] = int(m.group(1))
    return r

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
                        cat=c, tags=[tag] + (["닷컴ONLY"] if only and tag != "닷컴ONLY" else []),
                        model=(re.search(r"\b(?=[A-Z0-9\-\.]*\d)(?=[A-Z0-9\-\.]*[A-Z])[A-Z0-9][A-Z0-9\-\.]{5,}\b", t) or [""])[0], txt=t[:1500], **dd(t))
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
                                cat=SLUG.get(url.split("/")[1], "기타"), tags=["닷컴ONLY"], model=str(f.get("sku") or f.get("salesModelCode") or ""),
                                txt=" ".join(str(x) for x in f.values() if isinstance(x, str))[:1500])
        for v in o.values(): find_products(v, res)
    elif isinstance(o, list):
        for v in o: find_products(v, res)

def search_only():
    from playwright.sync_api import sync_playwright
    res, log, fail, cnt, keys = {}, [], "", "", ""
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(user_agent=UA["User-Agent"])
        kw = urllib.parse.quote("닷컴ONLY")
        pg.goto(B + "/sch?keyword=" + kw + "&tab=all", wait_until="networkidle", timeout=90000)
        H = {"Origin": B, "Referer": B + "/", "Accept": "application/json"}
        try:
            cnt = pg.context.request.get("https://apiv2.lge.co.kr/searchsvc/ajax/v2/search/product-count?keyword=%s&sort=BEST&page=1&size=20" % kw, headers=H, timeout=60000).text()[:400]
        except Exception as e:
            cnt = str(e)[:200]
        stale = 0
        for page in range(1, 80):
            u = "https://apiv2.lge.co.kr/searchsvc/ajax/v2/search/product?keyword=%s&attrs=&sort=BEST&page=%d&size=100" % (kw, page)
            txt = pg.context.request.get(u, headers=H, timeout=60000).text()
            try: j = json.loads(txt)
            except Exception: log.append("p%d:JSON아님" % page); break
            d = j.get("data") if isinstance(j, dict) else None
            lst = d.get("list") if isinstance(d, dict) else None
            if page == 1 and isinstance(d, dict): keys = ",".join("%s=%s" % (k, v) for k, v in d.items() if not isinstance(v, (list, dict)))[:300]
            n, new = (len(lst) if isinstance(lst, list) else -1), 0
            for el in (lst if isinstance(lst, list) else [j]):
                tmp = {}
                find_products(el, tmp)
                if not tmp and not fail: fail = json.dumps(el, ensure_ascii=False)[:800]
                for k, v in tmp.items():
                    if k not in res: res[k] = v; new += 1
            log.append("p%d:목록%d/신규%d" % (page, n, new))
            stale = stale + 1 if new == 0 else 0
            if n == 0 or stale >= 3: break
        b.close()
    status["debug"] = {"count": "수집 %d" % len(res), "pages": " ".join(log), "info": keys, "total_api": cnt, "fail_sample": fail}
    if not res:
        status["errors"].append("닷컴ONLY 0건 - 진단 저장됨")
    return res

FR = ("냉장고", "김치냉장고", "컨버터블 패키지", "와인셀러")
WS = ("세탁기", "건조기", "워시타워", "워시콤보")

def enrich(v):
    m = (v.get("model") or v["url"].split("/")[-1].split("-")[0]).upper()
    v["model"] = m
    t = v.pop("txt", "") + " " + v["name"]
    c, sub, n = v["cat"], "", 0
    if c == "TV":
        x, cm = re.match(r"(\d{2,3})", m), re.search(r"(\d{2,3})\s*cm", t)
        n = int(x.group(1)) if x and 20 <= int(x.group(1)) <= 110 else (min([24, 28, 32, 43, 48, 50, 55, 65, 75, 77, 83, 85, 86, 97, 98], key=lambda z: abs(z - int(cm.group(1)) / 2.54)) if cm else 0)
        sub = "%d인치" % n if n else ""
    elif c == "노트북":
        x, cm = re.match(r"(\d{2})", m), re.search(r"(\d{2}(?:\.\d)?)\s*cm", t)
        n = int(x.group(1)) if x and 11 <= int(x.group(1)) <= 18 else (round(float(cm.group(1)) / 2.54) if cm else 0)
        sub = "%d인치" % n if 11 <= n <= 18 else ""
    elif c in FR:
        x = re.search(r"(\d{3,4})\s*L\b", t) or re.match(r"[A-Z]{1,2}(\d{3})", m)
        n = int(x.group(1)) if x else 0
        sub = ("300L 미만" if n < 300 else "%dL대" % (n // 100 * 100)) if n else ""
    elif c in WS:
        x = re.search(r"(\d{1,2})\s*kg", t, re.I) or re.match(r"[A-Z]{1,2}(\d{2})", m)
        n = int(x.group(1)) if x else 0
        sub = "%dkg" % n if 5 <= n <= 30 else ""
    v["sub"], v["subn"] = sub, n

items, status = {}, {"errors": []}
def merge(d):
    for u, v in d.items():
        if u in items:
            items[u]["tags"] = sorted(set(items[u]["tags"] + v["tags"]))
            items[u]["price"] = min(items[u]["price"], v["price"])
            items[u]["img"] = items[u]["img"] or v["img"]
            for k in ("dday", "stock"):
                if k in v: items[u][k] = v[k]
            items[u]["model"] = items[u].get("model") or v.get("model", "")
            items[u]["txt"] = items[u].get("txt", "") + " " + v.get("txt", "")
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
for v in items.values():
    enrich(v)
if items:
    kst = datetime.timezone(datetime.timedelta(hours=9))
    json.dump({"updated": datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M"), "status": status,
               "items": sorted(items.values(), key=lambda x: (x["cat"], x["price"]))},
              open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
else:
    raise SystemExit("수집 0건 - 기존 데이터 유지: %s" % status)
