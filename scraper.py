"""HOMES.co.jp 物件爬蟲模組"""

import json
import os
import re
import time
from bs4 import BeautifulSoup

CACHE_FILE = os.path.join(os.path.dirname(__file__), "teiki_cache.json")


def load_teiki_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_teiki_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def get_teiki(station_name):
    """TEIKI_TABLE → cache の順で定期代を取得。None なら未知。"""
    t = TEIKI_TABLE.get(station_name)
    if t is not None:
        return t
    cache = load_teiki_cache()
    c = cache.get(station_name)
    if c is not None:
        return c
    return None

BASIC_FIELDS = {
    "賃料": "rent", "管理費等": "mgmt", "敷金/礼金": "deposit",
    "交通": "station", "所在地": "address", "築年月": "built",
    "間取り": "layout", "主要採光面": "orientation", "専有面積": "area",
    "所在階/階数": "floor", "現況": "status", "入居可能時期": "movein",
}
DETAIL_FIELDS = {
    "位置": "position", "入居条件": "conditions",
    "キッチン": "kitchen", "バス・トイレ": "bath",
    "設備・サービス": "facilities", "その他": "others", "備考": "remarks",
}
BUILDING_FIELDS = {
    "建物構造": "structure", "駐車場": "parking", "総戸数": "total_units",
    "契約期間": "contract_period", "保証会社": "guarantor",
    "住宅保険": "insurance", "管理": "management", "取引態様": "transaction_type",
}
SURROUNDINGS_CATEGORIES = {
    "買い物": "shopping", "医療": "medical", "学校": "school",
    "その他施設": "other_facilities", "公共機関": "public", "金融機関": "finance",
}

# 定期代テーブル (駅名 → 1ヶ月定期代)
# デフォルトは大阪メトロ(本町行き)のデータ。他都市はteiki_cache.jsonまたはNAVITIME検索で対応。
TEIKI_TABLE = {
    # 御堂筋線
    "江坂": 11030, "新大阪": 9480, "西中島南方": 9480, "中津": 7930,
    "梅田": 7930, "淀屋橋": 7930, "本町": 0, "心斎橋": 7930,
    "なんば": 7930, "大国町": 9480, "動物園前": 9480, "天王寺": 9480,
    "昭和町": 9480, "西田辺": 11030, "長居": 11030, "あびこ": 11030,
    "北花田": 11830, "新金岡": 11830, "なかもず": 11830, "中百舌鳥": 11830,
    # 谷町線
    "大日": 11830, "守口": 11830, "太子橋今市": 11030, "千林大宮": 11030,
    "関目高殿": 11030, "野江内代": 11030, "都島": 11030,
    "天神橋筋六丁目": 9480, "南森町": 7930, "天満橋": 7930,
    "谷町四丁目": 7930, "谷町六丁目": 7930, "谷町九丁目": 9480,
    "四天王寺前夕陽ヶ丘": 9480, "天王寺": 9480, "阿倍野": 9480,
    "文の里": 9480, "田辺": 11030, "駒川中野": 11030,
    "平野": 11030, "喜連瓜破": 11830, "出戸": 11830,
    "長原": 11830, "八尾南": 11830,
    # 四つ橋線
    "西梅田": 7930, "肥後橋": 7930, "四ツ橋": 7930, "なんば": 7930,
    "大国町": 9480, "花園町": 9480, "岸里": 9480, "玉出": 9480,
    "北加賀屋": 11030, "住之江公園": 11030,
    # 中央線
    "コスモスクエア": 11030, "大阪港": 9480, "朝潮橋": 9480,
    "弁天町": 9480, "九条": 7930, "阿波座": 7930,
    "堺筋本町": 7930, "森ノ宮": 9480, "緑橋": 9480,
    "深江橋": 9480, "高井田": 11030, "長田": 11030,
    # 千日前線
    "野田阪神": 7930, "玉川": 7930, "阿波座": 7930,
    "西長堀": 7930, "桜川": 7930, "なんば": 7930,
    "日本橋": 7930, "谷町九丁目": 9480, "鶴橋": 9480,
    "今里": 9480, "新深江": 11030, "小路": 11030, "北巽": 11030, "南巽": 11030,
    # 堺筋線
    "天神橋筋六丁目": 9480, "扇町": 9480, "南森町": 7930,
    "北浜": 7930, "堺筋本町": 7930, "長堀橋": 7930,
    "日本橋": 7930, "恵美須町": 9480, "動物園前": 9480, "天下茶屋": 9480,
    # 長堀鶴見緑地線
    "大正": 9480, "ドーム前千代崎": 9480, "西長堀": 7930, "西大橋": 7930,
    "心斎橋": 7930, "長堀橋": 7930, "松屋町": 7930, "谷町六丁目": 7930,
    "玉造": 9480, "森ノ宮": 9480, "大阪ビジネスパーク": 9480,
    "京橋": 9480, "蒲生四丁目": 9480, "今福鶴見": 11030,
    "横堤": 11030, "鶴見緑地": 11030, "門真南": 11030,
    # 今里筋線
    "井高野": 11830, "瑞光四丁目": 11830, "だいどう豊里": 11830,
    "太子橋今市": 11030, "清水": 11030, "新森古市": 11030,
    "関目成育": 11030, "蒲生四丁目": 9480, "鴫野": 9480,
    "緑橋": 9480, "今里": 9480,
    # JR (概算 - 要乗り換え)
    "玉造": 12240, "鶴橋": 9480, "桜ノ宮": 11030,
    "大阪城北詰": 12240, "芦原橋": 13790, "杉本町": 15340,
    "我孫子町": 15340,
    # 近鉄
    "大阪上本町": 9480,
    # 南海
    "今宮戎": 9480, "岸里玉出": 9480, "芦原町": 13790,
    "西天下茶屋": 16440, "津守": 16440, "塚西": 9480,
    # 京阪
    "野江": 11030,
    # 阪急
    "十三": 9480,
}


def parse_property(html, url):
    """HTMLから物件情報を抽出"""
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ")

    # タイトルからラベル取得
    title_tag = soup.find("title")
    label = "不明"
    if title_tag:
        title_text = title_tag.string or title_tag.get_text()
        if title_text:
            # HOMES format: "賃貸！物件名 階数！..." or "...！物件名/..."
            parts = title_text.split("！")
            if len(parts) > 1:
                label = parts[1].split("[")[0].split("/")[0].strip()
            elif "｜" in title_text:
                label = title_text.split("｜")[0].strip()
            elif "|" in title_text:
                label = title_text.split("|")[0].strip()
            else:
                label = title_text.strip()[:60]
    # fallback: h1 or og:title
    if label == "不明":
        h1 = soup.find("h1")
        if h1:
            label = h1.get_text(strip=True)[:60]
    if label == "不明":
        og = soup.find("meta", {"property": "og:title"})
        if og and og.get("content"):
            label = og["content"].strip()[:60]

    r = {"label": label, "url": url}

    # 基本情報
    for dl in soup.find_all("dl"):
        for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
            l, v = dt.get_text(strip=True), dd.get_text(" ", strip=True)
            for jp, key in BASIC_FIELDS.items():
                if jp in l and key not in r:
                    r[key] = v
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            th, td = row.find("th"), row.find("td")
            if th and td:
                l, v = th.get_text(strip=True), td.get_text(" ", strip=True)
                for jp, key in BASIC_FIELDS.items():
                    if jp in l and key not in r:
                        r[key] = v
    for span in soup.find_all(["span", "th", "dt", "label", "p"]):
        txt = span.get_text(strip=True)
        for jp, key in BASIC_FIELDS.items():
            if (txt == jp or txt == jp + "：") and key not in r:
                sib = span.find_next_sibling()
                if sib:
                    r[key] = sib.get_text(strip=True)

    # ハイライト
    for ul in soup.find_all("ul"):
        cls = " ".join(ul.get("class", []))
        if "overflow-x-auto" in cls:
            items = [li.get_text(strip=True) for li in ul.find_all("li") if li.get_text(strip=True)]
            if items and any(kw in " ".join(items) for kw in ["敷金", "礼金", "階以上", "駐車場"]):
                r["highlights"] = items
                break

    # 詳細条件
    for ul in soup.find_all("ul"):
        for li in ul.find_all("li", recursive=False):
            lp = li.find("p", class_=lambda c: c and "bg-mono-50" in c)
            if not lp:
                continue
            l = lp.get_text(strip=True)
            vd = lp.find_next_sibling()
            if vd:
                v = vd.get_text(" ", strip=True)
                for jp, key in DETAIL_FIELDS.items():
                    if jp in l and key not in r and v:
                        r[key] = v

    # 周辺環境
    surr = {}
    for h3 in soup.find_all("h3"):
        h = h3.get_text(strip=True)
        for jp, key in SURROUNDINGS_CATEGORIES.items():
            if jp in h:
                nu = h3.find_next("ul")
                if nu:
                    items = [li.get_text(" ", strip=True) for li in nu.find_all("li") if li.get_text(strip=True)]
                    if items:
                        surr[key] = items
    if surr:
        r["surroundings"] = surr

    # 建物概要
    bldg = {}
    for dl in soup.find_all("dl"):
        for div in dl.find_all("div"):
            dt, dd = div.find("dt"), div.find("dd")
            if dt and dd:
                l, v = dt.get_text(strip=True), dd.get_text(" ", strip=True)
                for jp, key in BUILDING_FIELDS.items():
                    if jp in l and key not in bldg and v:
                        bldg[key] = v
    if bldg:
        r["building"] = bldg

    # 外国人
    r["foreigner"] = "不明"
    for pat, val in [("外国人不可", "✗ 不可"), ("外国籍不可", "✗ 不可"),
                     ("外国人フレンドリー", "✓ 可"), ("外国人可", "✓ 可"),
                     ("外国籍可", "✓ 可"), ("外国人入居相談", "△ 要相談")]:
        if pat in full_text:
            r["foreigner"] = val
            break

    return r


def parse_suumo(html, url):
    """SUUMO物件ページからデータを抽出"""
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ")
    r = {"url": url, "source": "suumo"}

    # タイトルから物件名
    title_tag = soup.find("title")
    title_text = (title_tag.string or title_tag.get_text()) if title_tag else ""
    if title_text:
        # 【SUUMO】1K/4階/25.5m2／大阪府...／九条駅の賃貸
        # Try to get building name from h1 first
        h1 = soup.find("h1")
        if h1:
            r["label"] = h1.get_text(strip=True)[:60]
        elif "／" in title_text:
            r["label"] = title_text.split("／")[-1].split("の賃貸")[0].strip()
        else:
            r["label"] = title_text.replace("【SUUMO】", "").strip()[:60] or "SUUMO物件"
    else:
        r["label"] = "SUUMO物件"

    # table th/td でデータ取得
    suumo_fields = {
        "所在地": "address", "駅徒歩": "station", "間取り": "layout",
        "築年数": "built", "向き": "orientation", "間取り詳細": "layout_detail",
        "階建": "floor", "入居": "movein", "条件": "conditions",
        "契約期間": "contract_period", "保証会社": "guarantor", "備考": "remarks",
        "損保": "insurance",
    }
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                lbl = th.get_text(strip=True)
                val = td.get_text(" ", strip=True)
                for jp, key in suumo_fields.items():
                    if jp == lbl and key not in r:
                        r[key] = val

    # 賃料・管理費・敷金・礼金（property_view_note-list から）
    for div in soup.find_all("div", class_="property_view_note-list"):
        txt = div.get_text(" ", strip=True)
        if "管理費" in txt:
            m_rent = re.search(r'([\d.]+)万円', txt)
            if m_rent:
                r["rent"] = f"{m_rent.group(1)}万円"
            m_mgmt = re.search(r'管理費[・共益費]*[:：]?\s*([\d,]+)円', txt)
            if m_mgmt:
                r["mgmt"] = f"{m_mgmt.group(1)}円"
        if "敷金" in txt and "礼金" in txt:
            m_shiki = re.search(r'敷金[:：]?\s*([\d.]+万円|-)', txt)
            m_rei = re.search(r'礼金[:：]?\s*([\d.]+万円|-)', txt)
            shiki = m_shiki.group(1) if m_shiki else "-"
            rei = m_rei.group(1) if m_rei else "-"
            shiki = "無" if shiki == "-" else shiki
            rei = "無" if rei == "-" else rei
            r["deposit"] = f"{shiki}/{rei}"

    # 面積（タイトル → テーブル → 間取り詳細 → 本文から取得）
    area_found = False
    if title_tag and (title_tag.string or title_tag.get_text()):
        title_text = title_tag.string or title_tag.get_text()
        m_area = re.search(r'([\d.]+)\s*m[2²㎡]', title_text)
        if m_area:
            r["area"] = f"{m_area.group(1)}㎡"
            area_found = True
    if not area_found:
        # テーブルから「専有面積」を探す
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                th, td = row.find("th"), row.find("td")
                if th and td and "面積" in th.get_text(strip=True):
                    m_area = re.search(r'([\d.]+)', td.get_text(strip=True))
                    if m_area:
                        r["area"] = f"{m_area.group(1)}㎡"
                        area_found = True
                        break
            if area_found:
                break
    if not area_found:
        # 本文から面積を探す
        m_area = re.search(r'([\d.]+)\s*[m㎡][2²]?', full_text)
        if m_area and float(m_area.group(1)) > 10 and float(m_area.group(1)) < 200:
            r["area"] = f"{m_area.group(1)}㎡"

    # 駅徒歩を HOMES 形式に変換
    # SUUMO format A: "地下鉄中央線/九条駅 歩3分"  (slash separator)
    # SUUMO format B: "沖縄都市モノレール おもろまち駅 徒歩4分"  (space separator, already HOMES-like)
    station_raw = r.get("station", "")
    # Try slash format first
    stations_slash = re.findall(r'([\w・ー/]+?)/(\S+駅)\s*歩(\d+)分', station_raw)
    if stations_slash:
        parts = []
        for line, st, walk in stations_slash:
            parts.append(f"{line} {st} 徒歩{walk}分")
        r["station"] = " ".join(parts)
    else:
        # Already in HOMES-like format or other — normalize "歩X分" to "徒歩X分"
        r["station"] = re.sub(r'歩(\d+)分', r'徒歩\1分', station_raw)

    # 築年数パース "築11年" → "20XX年"
    built_raw = r.get("built", "")
    m_age = re.search(r'築(\d+)年', built_raw)
    if m_age:
        age = int(m_age.group(1))
        year = 2026 - age
        r["built"] = f"{year}年 ({built_raw})"

    # 建物情報
    building = {}
    if r.get("contract_period"):
        building["contract_period"] = r.pop("contract_period")
    if r.get("guarantor"):
        building["guarantor"] = r.pop("guarantor")
    if r.get("insurance"):
        building["insurance"] = "要" if r.get("insurance") and r["insurance"] != "-" else "不要"
        building["insurance_detail"] = r.pop("insurance")

    # 階数パース "4階/15階建"
    floor_raw = r.get("floor", "")
    if "/" not in floor_raw and title_tag and title_tag.string:
        m_fl = re.search(r'(\d+)階', title_tag.string)
        if m_fl and floor_raw:
            r["floor"] = f"{m_fl.group(1)}階/{floor_raw}"

    if building:
        r["building"] = building

    # 外国人
    r["foreigner"] = "不明"
    for pat, val in [("外国人不可", "✗ 不可"), ("外国籍不可", "✗ 不可"),
                     ("外国人フレンドリー", "✓ 可"), ("外国人可", "✓ 可"),
                     ("外国籍可", "✓ 可"), ("外国人入居相談", "△ 要相談")]:
        if pat in full_text:
            r["foreigner"] = val
            break

    return r


def analyze_property(prop, config=None):
    """物件を分析：定期代・月額合計・スコア計算（config で条件カスタマイズ可）"""
    if config is None:
        config = {
            "budget": 100000, "max_walk_min": 15,
            "scoring": {
                "corner": 30, "south": 20, "east_variants": 10, "north_penalty": -10,
                "high_floor_5f": 15, "mid_floor_3f": 5, "area_25": 5,
                "room_6_5": 10, "room_small_penalty": -5, "new_10yr": 10, "mid_20yr": 5,
                "within_budget": 10, "over_budget_penalty": -20, "immediate": 5, "free_internet": 5,
            },
            "preferences": {
                "corner_required": True, "preferred_orientation": ["南", "南東", "南西", "東"],
                "min_floor": 5, "min_area": 25, "min_room_size": 6.5,
            },
        }

    budget = config.get("budget", 88500)
    max_walk = config.get("max_walk_min", 15)
    sc = config.get("scoring", {})
    pref = config.get("preferences", {})

    # 賃料パース
    rent_m = re.search(r'([\d.]+)万', prop.get("rent", ""))
    rent = int(float(rent_m.group(1)) * 10000) if rent_m else 0

    # 管理費パース
    mgmt_s = prop.get("mgmt", "").replace(",", "").replace("円", "")
    mgmt_m = re.search(r'(\d+)', mgmt_s)
    mgmt = int(mgmt_m.group(1)) if mgmt_m else 0

    # 面積パース
    area_m = re.search(r'([\d.]+)', prop.get("area", ""))
    area = float(area_m.group(1)) if area_m else 0

    # 全駅抽出
    station_text = prop.get("station", "")
    all_stations = re.findall(r'([\w・ー]+線)\s+(\S+)駅\s+徒歩(\d+)分', station_text)

    # 最安定期代を探す（電車通勤の場合のみ）
    commute_mode = config.get("commute_mode", "train") if config else "train"
    best_teiki = None
    best_station = None
    best_line = None
    best_walk = None
    missing_stations = []
    for line, name, walk in all_stations:
        walk_min = int(walk)
        if walk_min > max_walk:
            continue
        if commute_mode == "train":
            teiki = get_teiki(name)
            if teiki is not None:
                if best_teiki is None or teiki < best_teiki:
                    best_teiki = teiki
                    best_station = name
                    best_line = line
                    best_walk = walk_min
            else:
                missing_stations.append(name)
        else:
            # 非電車通勤：記錄最近站但不計算定期代
            if best_station is None:
                best_station = name
                best_walk = walk_min
                best_line = line

    monthly_total = rent + mgmt + (best_teiki or 0)
    remaining = budget - monthly_total

    # 階数パース
    floor_m = re.search(r'(\d+)階/(\d+)階建', prop.get("floor", ""))
    floor_num = int(floor_m.group(1)) if floor_m else 0
    floor_total = int(floor_m.group(2)) if floor_m else 0

    # 向きパース
    orientation = prop.get("orientation", "-")

    # 築年数パース
    built_m = re.search(r'(\d{4})年', prop.get("built", ""))
    built_year = int(built_m.group(1)) if built_m else 0
    age = 2026 - built_year if built_year else 0

    # 洋室帖数パース
    # 洋室帖数: HOMES "洋室 9.3帖" / SUUMO layout_detail "洋8.9 K3.1"
    room_m = re.search(r'洋室\s*([\d.]+)帖', prop.get("layout", ""))
    if not room_m:
        room_m = re.search(r'洋\s*([\d.]+)', prop.get("layout_detail", "") or prop.get("layout", ""))
    room_size = float(room_m.group(1)) if room_m else 0

    # 角部屋
    is_corner = "角部屋" in prop.get("position", "")

    # スコア計算
    score = 0
    if is_corner:
        score += sc.get("corner", 30)
    if orientation == "南":
        score += sc.get("south", 20)
    elif orientation in pref.get("preferred_orientation", ["東", "南東", "南西"]):
        score += sc.get("east_variants", 10)
    elif orientation == "北":
        score += sc.get("north_penalty", -10)
    if floor_num >= pref.get("min_floor", 5):
        score += sc.get("high_floor_5f", 15)
    elif floor_num >= 3:
        score += sc.get("mid_floor_3f", 5)
    if area >= pref.get("min_area", 25):
        score += sc.get("area_25", 5)
    if room_size >= pref.get("min_room_size", 6.5):
        score += sc.get("room_6_5", 10)
    elif room_size > 0:
        score += sc.get("room_small_penalty", -5)
    if age <= 10:
        score += sc.get("new_10yr", 10)
    elif age <= 20:
        score += sc.get("mid_20yr", 5)
    if remaining >= 0:
        score += sc.get("within_budget", 10)
    else:
        score += sc.get("over_budget_penalty", -20)
    if "即時" in prop.get("movein", "") or "即" in prop.get("movein", ""):
        score += sc.get("immediate", 5)
    if "インターネット使用料無料" in prop.get("facilities", ""):
        score += sc.get("free_internet", 5)

    # ── 初期費用計算 ──
    deposit_text = prop.get("deposit", "")
    building = prop.get("building", {})
    remarks = prop.get("remarks", "")

    # 敷金パース
    shikikin = 0
    shikikin_text = "無"
    dep_parts = deposit_text.split("/")
    if len(dep_parts) >= 1:
        dp = dep_parts[0].strip()
        m_dep = re.search(r'([\d.]+)ヶ月', dp)
        m_yen = re.search(r'([\d,]+)万?円', dp.replace(",", ""))
        if m_dep:
            shikikin = int(float(m_dep.group(1)) * rent)
            shikikin_text = dp
        elif m_yen:
            val = int(m_yen.group(1).replace(",", ""))
            shikikin = val * 10000 if "万" in dp else val
            shikikin_text = dp
        elif "無" in dp:
            shikikin_text = "無"

    # 礼金パース
    reikin = 0
    reikin_text = "無"
    if len(dep_parts) >= 2:
        rp = dep_parts[1].strip()
        m_rei = re.search(r'([\d.]+)ヶ月', rp)
        m_yen2 = re.search(r'([\d,]+)万?円', rp.replace(",", ""))
        if m_rei:
            reikin = int(float(m_rei.group(1)) * rent)
            reikin_text = rp
        elif m_yen2:
            val = int(m_yen2.group(1).replace(",", ""))
            reikin = val * 10000 if "万" in rp else val
            reikin_text = rp
        elif "無" in rp:
            reikin_text = "無"

    # 保証会社初回料パース
    guarantor_text = building.get("guarantor", "")
    hoshou_init = 0
    hoshou_text = ""
    m_pct = re.search(r'初回[^%]*?([\d]+)[％%]', guarantor_text)
    m_pct2 = re.search(r'初回保証[^:：]*[:：]\s*総?賃料の?([\d]+)[％%]', guarantor_text)
    m_yen3 = re.search(r'初回[^円]*?([\d,]+)円', guarantor_text.replace(",", ""))
    m_fixed = re.search(r'契約時[^円]*?([\d,]+)円', guarantor_text.replace(",", ""))
    if m_pct2:
        pct = int(m_pct2.group(1))
        hoshou_init = int((rent + mgmt) * pct / 100)
        hoshou_text = f"総賃料の{pct}%"
    elif m_pct:
        pct = int(m_pct.group(1))
        hoshou_init = int((rent + mgmt) * pct / 100)
        hoshou_text = f"総賃料の{pct}%"
    elif m_yen3:
        hoshou_init = int(m_yen3.group(1))
        hoshou_text = f"{hoshou_init:,}円"
    elif m_fixed:
        hoshou_init = int(m_fixed.group(1))
        hoshou_text = f"{hoshou_init:,}円"

    # 仲介手数料（一般的に賃料1ヶ月、仲介手数料無料の記載がある場合は0）
    chukai = rent
    chukai_text = "賃料1ヶ月"
    if "仲介手数料無料" in remarks or "仲介手数料不要" in remarks:
        chukai = 0
        chukai_text = "無料"

    # 初月家賃
    first_month = rent + mgmt

    # 火災保険（概算15,000〜20,000円）
    hoken = 20000 if building.get("insurance") == "要" else 0

    # 初期費用合計
    initial_cost = shikikin + reikin + hoshou_init + chukai + first_month + hoken

    # 月額追加費用（水道代、サポート費等）
    monthly_extras = re.findall(r'([\w・]+?)([\d,]+)円\s*\(月額\)', remarks)
    extra_monthly = sum(int(m[1].replace(",", "")) for m in monthly_extras)
    extra_monthly_text = ", ".join(f"{m[0]}{m[1]}円" for m in monthly_extras) if monthly_extras else ""

    return {
        **prop,
        "rent_num": rent,
        "mgmt_num": mgmt,
        "area_num": area,
        "best_teiki": best_teiki,
        "best_station": best_station,
        "best_line": best_line,
        "best_walk": best_walk,
        "missing_stations": missing_stations,
        "monthly_total": monthly_total + extra_monthly,
        "remaining": budget - (monthly_total + extra_monthly),
        "floor_num": floor_num,
        "floor_total": floor_total,
        "orientation": orientation,
        "built_year": built_year,
        "age": age,
        "room_size": room_size,
        "is_corner": is_corner,
        "score": score,
        "within_budget": (budget - (monthly_total + extra_monthly)) >= 0,
        # 初期費用
        "shikikin": shikikin,
        "shikikin_text": shikikin_text,
        "reikin": reikin,
        "reikin_text": reikin_text,
        "hoshou_init": hoshou_init,
        "hoshou_text": hoshou_text,
        "chukai": chukai,
        "chukai_text": chukai_text,
        "first_month": first_month,
        "hoken": hoken,
        "initial_cost": initial_cost,
        "extra_monthly": extra_monthly,
        "extra_monthly_text": extra_monthly_text,
    }
