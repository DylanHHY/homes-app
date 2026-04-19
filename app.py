#!/usr/bin/env python3
"""HOMES.co.jp 物件分析 Web App"""

import json
import os
import re
import time
import threading
from flask import Flask, render_template, request, jsonify
from scraper import parse_property, parse_suumo, analyze_property

app = Flask(__name__)
DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "salary": 250000,
    "fixed_expenses": 150000,
    "budget": 100000,
    "office_address": "",
    "office_label": "",
    "lang": "zh",
    "city_label": "",
    "commute_mode": "train",
    "metro_lines": [],
    "current_commute": 0,
    "current_address": "",
    "max_walk_min": 15,
    "scoring": {
        "corner": 30,
        "south": 20,
        "east_variants": 10,
        "north_penalty": -10,
        "high_floor_5f": 15,
        "mid_floor_3f": 5,
        "area_25": 5,
        "room_6_5": 10,
        "room_small_penalty": -5,
        "new_10yr": 10,
        "mid_20yr": 5,
        "within_budget": 10,
        "over_budget_penalty": -20,
        "immediate": 5,
        "free_internet": 5,
    },
    "preferences": {
        "corner_required": True,
        "preferred_orientation": ["南", "南東", "南西", "東"],
        "min_floor": 5,
        "min_area": 25,
        "min_room_size": 6.5,
    }
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        # merge with defaults
        config = {**DEFAULT_CONFIG, **saved}
        config["scoring"] = {**DEFAULT_CONFIG["scoring"], **saved.get("scoring", {})}
        config["preferences"] = {**DEFAULT_CONFIG["preferences"], **saved.get("preferences", {})}
        return config
    return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 進行状況管理
progress = {"status": "idle", "current": 0, "total": 0, "message": "", "results": []}


def load_data():
    """ファイルから保存済みデータを読み込む"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_data(results):
    """結果をファイルに保存"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


COMMUTE_KEYS = ("commute_min", "commute_transit", "commute_walk", "commute_station", "commute_route")


def merge_results(existing, new_results):
    """既存データと新規データをマージ（URLで重複排除、新しい方を優先、通勤データは保持）"""
    by_url = {}
    for r in existing:
        url = r.get("url", "")
        if url:
            by_url[url] = r
    for r in new_results:
        url = r.get("url", "")
        if url:
            # 既存の通勤データを保持
            old = by_url.get(url)
            if old:
                for key in COMMUTE_KEYS:
                    if r.get(key) is None and old.get(key) is not None:
                        r[key] = old[key]
            by_url[url] = r
    merged = list(by_url.values())
    merged.sort(key=lambda x: (-x.get("score", 0), x.get("monthly_total", 0)))
    return merged


def scrape_urls(urls):
    """バックグラウンドで物件をスクレイピング"""
    global progress
    progress = {"status": "running", "current": 0, "total": len(urls), "message": "ブラウザ起動中...", "results": []}

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="ja-JP",
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()

            # HOMES の場合は先にトップページでクッキー取得
            has_homes = any("homes.co.jp" in u for u in urls)
            if has_homes:
                progress["message"] = "HOMES首頁に接続中..."
                page.goto("https://www.homes.co.jp/chintai/", wait_until="domcontentloaded", timeout=30000)
                time.sleep(1)

            new_results = []
            for i, url in enumerate(urls):
                progress["current"] = i + 1
                progress["message"] = f"物件 {i+1}/{len(urls)} を取得中..."

                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                deadline = time.time() + 120
                ok = False
                while time.time() < deadline:
                    text = page.inner_text("body")
                    if "賃料" in text or "万円" in text or len(text) > 2000:
                        ok = True
                        break
                    if "Let's confirm you are human" in text:
                        progress["message"] = f"物件 {i+1}/{len(urls)}: 人機驗證中、ブラウザで「Begin」をクリック..."
                    time.sleep(2)

                if ok:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)
                    page.evaluate("window.scrollTo(0, 0)")
                    time.sleep(1)
                    if "suumo.jp" in url:
                        prop = parse_suumo(page.content(), url)
                    else:
                        prop = parse_property(page.content(), url)
                    analyzed = analyze_property(prop, load_config())
                    new_results.append(analyzed)
                    progress["message"] = f"物件 {i+1}/{len(urls)}: {analyzed.get('label','?')} ✓"
                else:
                    new_results.append({"label": "取得失敗", "url": url, "error": "timeout", "score": -100, "monthly_total": 999999, "within_budget": False})

                time.sleep(3)

            browser.close()

        # 既存データとマージして保存
        existing = load_data()
        merged = merge_results(existing, new_results)
        save_data(merged)

        # 未知駅があれば自動で定期代検索をキューに入れる
        all_missing = set()
        for r in merged:
            for st in r.get("missing_stations", []):
                all_missing.add(st)

        progress["results"] = merged
        progress["status"] = "done"
        if all_missing:
            progress["message"] = f"完了！{len(new_results)}件追加（{len(all_missing)}駅の定期代が未知→「定期代検索」で取得可能）"
        else:
            progress["message"] = f"完了！新規{len(new_results)}件を追加、合計{len(merged)}件"

    except Exception as e:
        progress["status"] = "error"
        progress["message"] = f"エラー: {str(e)}"


@app.route("/")
def index():
    config = load_config()
    return render_template("index.html", city_label=config.get("city_label", ""))


@app.route("/api/config")
def api_get_config():
    return jsonify(load_config())


@app.route("/api/config", methods=["POST"])
def api_save_config():
    config = request.json
    save_config(config)
    # 設定変更後、全物件を再分析
    data = load_data()
    commute_backup = {}
    for d in data:
        url = d.get("url", "")
        if d.get("commute_min") is not None:
            commute_backup[url] = {k: d[k] for k in COMMUTE_KEYS if k in d}
    results = [analyze_property(d, config) for d in data]
    for r in results:
        url = r.get("url", "")
        if url in commute_backup:
            for k, v in commute_backup[url].items():
                if r.get(k) is None:
                    r[k] = v
    results.sort(key=lambda x: (-x.get("score", 0), x.get("monthly_total", 0)))
    save_data(results)
    return jsonify({"message": "設定を保存し、全物件を再分析しました", "count": len(results)})


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    data = request.json
    urls_text = data.get("urls", "")
    # 支援 HOMES + SUUMO URL
    homes_pattern = r'https://www\.homes\.co\.jp/chintai/(?:b-[\w/]+|room/[\w]+/[^\s]*)'
    suumo_pattern = r'https://suumo\.jp/chintai/[^\s]+'
    homes_urls = re.findall(homes_pattern, urls_text)
    suumo_urls = re.findall(suumo_pattern, urls_text)
    # 清理
    cleaned = []
    for u in homes_urls:
        u = u.rstrip()
        if '/chintai/b-' in u and not u.endswith('/'):
            u += '/'
        cleaned.append(u)
    for u in suumo_urls:
        cleaned.append(u.rstrip())
    urls = list(dict.fromkeys(cleaned))

    if not urls:
        return jsonify({"error": "有効なHOMES URLが見つかりません"}), 400

    # 既に保存済みのURLを除外するオプション
    skip_existing = data.get("skip_existing", False)
    if skip_existing:
        existing_urls = {r.get("url") for r in load_data()}
        urls = [u for u in urls if u not in existing_urls]
        if not urls:
            return jsonify({"error": "全てのURLは既に分析済みです"}), 400

    thread = threading.Thread(target=scrape_urls, args=(urls,))
    thread.start()

    return jsonify({"message": f"{len(urls)}件の物件を取得開始", "count": len(urls)})


@app.route("/api/progress")
def api_progress():
    return jsonify(progress)


@app.route("/api/data")
def api_get_data():
    """保存済みデータを返す"""
    return jsonify(load_data())


@app.route("/api/analyze", methods=["POST"])
def api_analyze_existing():
    """既存JSONデータを分析して保存"""
    data = request.json
    properties = data.get("properties", [])
    config = load_config()
    results = [analyze_property(p, config) for p in properties]

    # 既存データとマージして保存
    existing = load_data()
    merged = merge_results(existing, results)
    save_data(merged)

    return jsonify(merged)


@app.route("/api/delete", methods=["POST"])
def api_delete():
    """物件を削除"""
    data = request.json
    url_to_delete = data.get("url", "")
    existing = load_data()
    filtered = [r for r in existing if r.get("url") != url_to_delete]
    save_data(filtered)
    return jsonify({"message": "削除しました", "count": len(filtered)})


@app.route("/api/delete-batch", methods=["POST"])
def api_delete_batch():
    """複数物件を一括削除"""
    data = request.json
    urls_to_delete = set(data.get("urls", []))
    existing = load_data()
    filtered = [r for r in existing if r.get("url") not in urls_to_delete]
    save_data(filtered)
    deleted = len(existing) - len(filtered)
    return jsonify({"message": f"{deleted}件を削除しました", "count": len(filtered)})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """全データ削除"""
    save_data([])
    return jsonify({"message": "全データを削除しました"})


# ── 通勤時間検索 ──────────────────────────────

def get_office_addr():
    return load_config().get("office_address", "")
commute_progress = {"status": "idle", "current": 0, "total": 0, "message": ""}


def find_best_station_for_commute(prop):
    """物件の交通情報から通勤用の最寄駅を探す。
    優先順: Metro駅(定期代既知) → 他路線(定期代既知) → 最寄駅(定期代不明でも)
    Returns (駅名, 徒歩分数, 路線名) or (None, None, None)
    """
    from scraper import TEIKI_TABLE, get_teiki
    station_text = prop.get("station", "")
    all_stations = re.findall(r'([\w・ー]+線)\s+(\S+)駅\s+徒歩(\d+)分', station_text)

    if not all_stations:
        return None, None, None

    config = load_config()
    configured_lines = config.get("metro_lines", [])
    metro_lines = set(configured_lines) if configured_lines else {
        "御堂筋線", "谷町線", "四つ橋線", "中央線", "千日前線",
        "堺筋線", "長堀鶴見緑地線", "今里筋線"
    }

    best_metro = None
    best_other = None
    first_station = None

    for line, name, walk in all_stations:
        walk_min = int(walk)
        teiki = get_teiki(name)
        is_metro = any(ml in line for ml in metro_lines)

        if first_station is None:
            first_station = (name, walk_min, line)

        if teiki is not None and is_metro:
            if best_metro is None or teiki < best_metro[3] or (teiki == best_metro[3] and walk_min < best_metro[1]):
                best_metro = (name, walk_min, line, teiki)
        elif teiki is not None:
            if best_other is None or teiki < best_other[3] or (teiki == best_other[3] and walk_min < best_other[1]):
                best_other = (name, walk_min, line, teiki)

    # Metro優先 → 他路線 → 最寄駅(定期代不明)
    if best_metro:
        return best_metro[0], best_metro[1], best_metro[2]
    if best_other:
        return best_other[0], best_other[1], best_other[2]
    # 定期代不明でも最寄駅名は返す（Google Maps用）
    return first_station


def lookup_commute_times(force_all=False):
    """Google Maps で全物件の通勤時間を検索（Metro駅起点）"""
    global commute_progress
    from playwright.sync_api import sync_playwright
    from urllib.parse import quote

    data = load_data()
    if force_all:
        targets = [r for r in data if r.get("address") or r.get("station")]
    else:
        targets = [r for r in data if r.get("commute_min") is None and (r.get("address") or r.get("station"))]

    commute_progress = {"status": "running", "current": 0, "total": len(targets), "message": "Google Maps を起動中..."}

    if not targets:
        commute_progress = {"status": "done", "current": 0, "total": 0, "message": "全物件の通勤時間は取得済みです"}
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
            ctx = browser.new_context(locale="ja-JP", viewport={"width": 1280, "height": 900})
            page = ctx.new_page()

            for i, prop in enumerate(targets):
                label = prop.get("label", "?")
                commute_progress["current"] = i + 1
                commute_progress["message"] = f"{i+1}/{len(targets)} {label}..."

                # 物件住所から直接検索（door-to-door）
                addr = prop.get("address", "").replace("地図を見る", "").strip()
                if not addr:
                    # 住所がなければ最寄駅で代用
                    best_st, walk_min, best_line = find_best_station_for_commute(prop)
                    config = load_config()
                    city = config.get("city_label", "")
                    addr = f"{best_st}駅 {city}".strip() if best_st else ""

                if not addr:
                    prop["commute_min"] = None
                    continue

                origin = quote(addr)
                dest = quote(get_office_addr())
                config = load_config()
                mode_map = {"train": "3", "car": "0", "bike": "1", "walk": "2"}
                mode_labels = {"train": "transit", "car": "car", "bike": "bike", "walk": "walk"}
                preferred = config.get("commute_mode", "train")
                # Build try order: preferred mode first, then others by speed
                all_modes = ["car", "train", "bike", "walk"]
                try_order = [preferred] + [m for m in all_modes if m != preferred]

                try:
                    best_time = None
                    best_route = None
                    best_mode_used = None

                    for mode in try_order:
                        gm_mode = mode_map.get(mode, "3")
                        maps_url = f"https://www.google.com/maps/dir/{origin}/{dest}/data=!4m2!4m1!3e{gm_mode}"

                        page.goto(maps_url, wait_until="domcontentloaded", timeout=20000)
                        time.sleep(10)

                        # Accept cookies first time
                        try:
                            page.locator('button:has-text("すべて承認"), button:has-text("Accept all")').first.click(timeout=3000)
                            time.sleep(2)
                        except:
                            pass

                        # Extract route info
                        routes = []
                        for attempt in range(2):
                            routes = page.evaluate("""
                            () => {
                                const sections = document.querySelectorAll('div[data-trip-index], .section-directions-trip');
                                return Array.from(sections).map(s => s.innerText.substring(0, 300));
                            }
                            """)
                            if routes:
                                break
                            if attempt < 1:
                                time.sleep(5)
                                page.reload(wait_until="domcontentloaded", timeout=15000)
                                time.sleep(8)

                        # Parse shortest time
                        for route_text in routes:
                            for line in route_text.split('\n'):
                                line = line.strip()
                                m = re.match(r'^(\d+)\s*分$', line)
                                if m:
                                    mins = int(m.group(1))
                                    if best_time is None or mins < best_time:
                                        best_time = mins
                                        best_route = route_text.replace('\n', ' | ')[:120]
                                        best_mode_used = mode
                                m2 = re.match(r'^(\d+)\s*時間\s*(\d+)\s*分$', line)
                                if m2:
                                    mins = int(m2.group(1)) * 60 + int(m2.group(2))
                                    if best_time is None or mins < best_time:
                                        best_time = mins
                                        best_route = route_text.replace('\n', ' | ')[:120]
                                        best_mode_used = mode

                        # Found result with preferred mode — stop here
                        if best_time is not None and mode == preferred:
                            break
                        # Found result with fallback — keep it but continue to see if preferred works
                        if best_time is not None and mode != preferred:
                            # Already have a fallback, no need to try slower modes
                            break

                    if best_time is not None:
                        prop["commute_min"] = best_time
                        prop["commute_route"] = best_route
                        prop["commute_mode_used"] = mode_labels.get(best_mode_used, best_mode_used)
                        mode_tag = "" if best_mode_used == preferred else f" [{mode_labels[best_mode_used]}]"
                        commute_progress["message"] = f"{i+1}/{len(targets)} {label}: {best_time}分{mode_tag} ✓"
                    else:
                        prop["commute_min"] = -1
                        prop["commute_route"] = None
                        prop["commute_mode_used"] = None
                        commute_progress["message"] = f"{i+1}/{len(targets)} {label}: 取得失敗"

                except Exception as e:
                    prop["commute_min"] = -1
                    prop["commute_route"] = None
                    prop["commute_mode_used"] = None
                    commute_progress["message"] = f"{i+1}/{len(targets)} {label}: エラー"

                time.sleep(1)

            browser.close()

        save_data(data)
        commute_progress["status"] = "done"
        commute_progress["message"] = f"完了！{len(targets)}件の通勤時間を取得しました"

    except Exception as e:
        commute_progress["status"] = "error"
        commute_progress["message"] = f"エラー: {str(e)}"


@app.route("/api/commute", methods=["POST"])
def api_commute():
    """全物件の通勤時間を検索開始"""
    data = request.json or {}
    force = data.get("force", False)
    thread = threading.Thread(target=lookup_commute_times, args=(force,))
    thread.start()
    return jsonify({"message": "通勤時間の検索を開始しました"})


@app.route("/api/commute/progress")
def api_commute_progress():
    return jsonify(commute_progress)


# ── 定期代自動検索 ──────────────────────────────

teiki_progress = {"status": "idle", "current": 0, "total": 0, "message": ""}


def lookup_missing_teiki():
    """data.json 内の missing_stations を NAVITIME で検索"""
    global teiki_progress
    from playwright.sync_api import sync_playwright
    from scraper import load_teiki_cache, save_teiki_cache, TEIKI_TABLE

    data = load_data()
    # 全物件から missing_stations を収集（重複排除）
    all_missing = set()
    for prop in data:
        for st in prop.get("missing_stations", []):
            if st not in TEIKI_TABLE and st not in load_teiki_cache():
                all_missing.add(st)

    if not all_missing:
        teiki_progress = {"status": "done", "current": 0, "total": 0, "message": "全駅の定期代は取得済みです"}
        return

    stations = sorted(all_missing)
    teiki_progress = {"status": "running", "current": 0, "total": len(stations), "message": "NAVITIME を起動中..."}

    cache = load_teiki_cache()
    config = load_config()
    dest_label = config.get("office_label", "")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )
            ctx = browser.new_context(locale="ja-JP", viewport={"width": 1280, "height": 900})
            page = ctx.new_page()

            for i, st in enumerate(stations):
                teiki_progress["current"] = i + 1
                teiki_progress["message"] = f"{i+1}/{len(stations)} {st}駅 → {dest_label}..."

                try:
                    page.goto("https://www.navitime.co.jp/transfer/pass/", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3)

                    dep = page.locator('input[name="orvStationName"]')
                    dep.click()
                    dep.fill("")
                    dep.type(st, delay=100)
                    time.sleep(1.5)
                    page.keyboard.press("ArrowDown")
                    time.sleep(0.3)
                    page.keyboard.press("Enter")
                    time.sleep(0.5)

                    arr = page.locator('input[name="dnvStationName"]')
                    arr.click()
                    arr.fill("")
                    arr.type(dest_label or "本町", delay=100)
                    time.sleep(1.5)
                    page.keyboard.press("ArrowDown")
                    time.sleep(0.3)
                    page.keyboard.press("Enter")
                    time.sleep(0.5)

                    try:
                        page.locator('button.btn_submit').click(timeout=10000)
                    except:
                        pass
                    time.sleep(5)

                    text = page.inner_text("body")
                    prices = re.findall(r'([\d,]+)円', text)
                    if prices and "result" in page.url:
                        monthly = int(prices[0].replace(",", ""))
                        cache[st] = monthly
                        teiki_progress["message"] = f"{i+1}/{len(stations)} {st}駅: {prices[0]}円 ✓"
                    else:
                        teiki_progress["message"] = f"{i+1}/{len(stations)} {st}駅: 取得失敗"

                except Exception as e:
                    teiki_progress["message"] = f"{i+1}/{len(stations)} {st}駅: エラー"

                time.sleep(1)

            browser.close()

        # キャッシュ保存
        save_teiki_cache(cache)

        # data.json を再分析（新しい定期代で更新）
        data = load_data()
        config = load_config()
        updated = [analyze_property(d, config) for d in data]
        updated.sort(key=lambda x: (-x.get("score", 0), x.get("monthly_total", 0)))
        save_data(updated)

        teiki_progress["status"] = "done"
        teiki_progress["message"] = f"完了！{len(stations)}駅の定期代を取得し、全物件を再計算しました"

    except Exception as e:
        teiki_progress["status"] = "error"
        teiki_progress["message"] = f"エラー: {str(e)}"


@app.route("/api/teiki", methods=["POST"])
def api_teiki():
    """未知駅の定期代を NAVITIME で検索"""
    thread = threading.Thread(target=lookup_missing_teiki)
    thread.start()
    return jsonify({"message": "定期代の検索を開始しました"})


@app.route("/api/teiki/progress")
def api_teiki_progress():
    return jsonify(teiki_progress)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
