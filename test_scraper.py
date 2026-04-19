"""scraper.py 單元測試"""

import pytest
from scraper import get_teiki, parse_property, parse_suumo, analyze_property, TEIKI_TABLE


# ── get_teiki ────────────────────────────────────

class TestGetTeiki:
    def test_known_station(self):
        assert get_teiki("本町") == 0
        assert get_teiki("梅田") == 7930

    def test_unknown_station(self):
        assert get_teiki("存在しない駅") is None

    def test_cache_fallback(self, tmp_path, monkeypatch):
        """TEIKI_TABLE にない駅でも cache にあれば返す"""
        import scraper
        monkeypatch.setattr(scraper, "CACHE_FILE", str(tmp_path / "cache.json"))

        # cache に書き込み
        scraper.save_teiki_cache({"テスト駅": 12345})
        assert get_teiki("テスト駅") == 12345


# ── parse_property (HOMES) ───────────────────────

HOMES_HTML = """
<html>
<head><title>賃貸！テストマンション 5階！大阪市中央区</title></head>
<body>
<dl>
  <dt>賃料</dt><dd>6.5万円</dd>
  <dt>管理費等</dt><dd>5,000円</dd>
  <dt>敷金/礼金</dt><dd>1ヶ月/無</dd>
  <dt>交通</dt><dd>御堂筋線 本町駅 徒歩5分 中央線 堺筋本町駅 徒歩8分</dd>
  <dt>所在地</dt><dd>大阪府大阪市中央区</dd>
  <dt>築年月</dt><dd>2020年3月</dd>
  <dt>間取り</dt><dd>1K 洋室 8.5帖</dd>
  <dt>主要採光面</dt><dd>南</dd>
  <dt>専有面積</dt><dd>25.5㎡</dd>
  <dt>所在階/階数</dt><dd>5階/10階建</dd>
  <dt>現況</dt><dd>空室</dd>
  <dt>入居可能時期</dt><dd>即時</dd>
</dl>
<ul>
  <li><p class="bg-mono-50">位置</p><p>角部屋</p></li>
  <li><p class="bg-mono-50">設備・サービス</p><p>インターネット使用料無料 エアコン</p></li>
</ul>
<p>外国人可</p>
</body>
</html>
"""


class TestParseProperty:
    def test_label(self):
        r = parse_property(HOMES_HTML, "https://www.homes.co.jp/chintai/b-123/")
        assert "テストマンション" in r["label"]

    def test_basic_fields(self):
        r = parse_property(HOMES_HTML, "https://www.homes.co.jp/chintai/b-123/")
        assert "6.5万円" in r["rent"]
        assert "5,000" in r["mgmt"]
        assert "本町駅" in r["station"]
        assert "25.5" in r["area"]
        assert "5階/10階建" in r["floor"]
        assert r["orientation"] == "南"
        assert "2020" in r["built"]
        assert "即時" in r["movein"]

    def test_deposit(self):
        r = parse_property(HOMES_HTML, "https://www.homes.co.jp/chintai/b-123/")
        assert "1ヶ月" in r["deposit"]

    def test_corner_and_facilities(self):
        r = parse_property(HOMES_HTML, "https://www.homes.co.jp/chintai/b-123/")
        assert r["position"] == "角部屋"
        assert "インターネット使用料無料" in r["facilities"]

    def test_foreigner(self):
        r = parse_property(HOMES_HTML, "https://www.homes.co.jp/chintai/b-123/")
        assert "可" in r["foreigner"]

    def test_url_preserved(self):
        url = "https://www.homes.co.jp/chintai/b-123/"
        r = parse_property(HOMES_HTML, url)
        assert r["url"] == url


# ── parse_suumo ──────────────────────────────────

SUUMO_HTML = """
<html>
<head><title>【SUUMO】1K/4階/25.5m2／大阪府大阪市中央区／九条駅の賃貸</title></head>
<body>
<h1>SUUMOテストマンション</h1>
<table>
  <tr><th>所在地</th><td>大阪府大阪市中央区</td></tr>
  <tr><th>駅徒歩</th><td>中央線/九条駅 歩5分</td></tr>
  <tr><th>間取り</th><td>1K</td></tr>
  <tr><th>築年数</th><td>築10年</td></tr>
  <tr><th>向き</th><td>南</td></tr>
  <tr><th>階建</th><td>15階建</td></tr>
  <tr><th>入居</th><td>即入居可</td></tr>
</table>
<div class="property_view_note-list">賃料 7.0万円 管理費・共益費：3,000円</div>
<div class="property_view_note-list">敷金：1万円 礼金：-</div>
</body>
</html>
"""


class TestParseSuumo:
    def test_label(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert r["label"] == "SUUMOテストマンション"

    def test_rent_and_mgmt(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert "7.0万円" in r["rent"]
        assert "3,000" in r["mgmt"]

    def test_station_normalization(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        # slash format → "中央線 九条駅 徒歩5分"
        assert "中央線" in r["station"]
        assert "九条駅" in r["station"]
        assert "徒歩5分" in r["station"]

    def test_built_year(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert "2016" in r["built"]

    def test_area_from_title(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert "25.5" in r["area"]

    def test_deposit(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert "deposit" in r
        # 礼金 "-" → "無"
        assert "無" in r["deposit"]

    def test_source_is_suumo(self):
        r = parse_suumo(SUUMO_HTML, "https://suumo.jp/chintai/xxx")
        assert r["source"] == "suumo"


# ── analyze_property ─────────────────────────────

class TestAnalyzeProperty:
    @pytest.fixture
    def base_prop(self):
        return {
            "label": "テスト物件",
            "url": "https://example.com/1",
            "rent": "6.5万円",
            "mgmt": "5,000円",
            "area": "26㎡",
            "station": "御堂筋線 本町駅 徒歩5分",
            "floor": "6階/10階建",
            "orientation": "南",
            "built": "2020年3月",
            "layout": "1K 洋室 8.5帖",
            "movein": "即時",
            "deposit": "無/無",
            "position": "角部屋",
            "facilities": "インターネット使用料無料 エアコン",
        }

    @pytest.fixture
    def config(self):
        return {
            "budget": 100000,
            "max_walk_min": 15,
            "commute_mode": "train",
            "scoring": {
                "corner": 30, "south": 20, "east_variants": 10,
                "north_penalty": -10, "high_floor_5f": 15, "mid_floor_3f": 5,
                "area_25": 5, "room_6_5": 10, "room_small_penalty": -5,
                "new_10yr": 10, "mid_20yr": 5, "within_budget": 10,
                "over_budget_penalty": -20, "immediate": 5, "free_internet": 5,
            },
            "preferences": {
                "corner_required": True,
                "preferred_orientation": ["南", "南東", "南西", "東"],
                "min_floor": 5, "min_area": 25, "min_room_size": 6.5,
            },
        }

    def test_rent_parse(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["rent_num"] == 65000

    def test_mgmt_parse(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["mgmt_num"] == 5000

    def test_area_parse(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["area_num"] == 26.0

    def test_floor_parse(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["floor_num"] == 6
        assert r["floor_total"] == 10

    def test_built_year(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["built_year"] == 2020
        assert r["age"] == 6

    def test_room_size(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["room_size"] == 8.5

    def test_is_corner(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["is_corner"] is True

    def test_teiki_found(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["best_station"] == "本町"
        assert r["best_teiki"] == 0  # 本町→本町 = 0

    def test_monthly_total(self, base_prop, config):
        r = analyze_property(base_prop, config)
        # 65000 + 5000 + 0 (本町定期代) = 70000
        assert r["monthly_total"] == 70000

    def test_within_budget(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["within_budget"] is True
        assert r["remaining"] == 30000

    def test_score_positive(self, base_prop, config):
        """角部屋+南向き+高層+面積OK+部屋OK+新築+予算内+即入居+無料net = 高分"""
        r = analyze_property(base_prop, config)
        # corner(30) + south(20) + high_floor(15) + area(5) + room(10) + new(10) + budget(10) + immediate(5) + internet(5)
        assert r["score"] == 110

    def test_score_north_penalty(self, base_prop, config):
        base_prop["orientation"] = "北"
        r = analyze_property(base_prop, config)
        assert r["score"] < 110  # 北向き = -10

    def test_over_budget(self, base_prop, config):
        config["budget"] = 50000
        r = analyze_property(base_prop, config)
        assert r["within_budget"] is False
        assert r["remaining"] < 0

    def test_initial_cost_no_deposit(self, base_prop, config):
        r = analyze_property(base_prop, config)
        assert r["shikikin"] == 0
        assert r["reikin"] == 0
        # 仲介手数料 = 賃料1ヶ月 = 65000
        assert r["chukai"] == 65000

    def test_initial_cost_with_deposit(self, base_prop, config):
        base_prop["deposit"] = "1ヶ月/1ヶ月"
        r = analyze_property(base_prop, config)
        assert r["shikikin"] == 65000
        assert r["reikin"] == 65000

    def test_missing_stations(self, base_prop, config):
        """TEIKI_TABLE にない駅が missing_stations に入る"""
        base_prop["station"] = "千日前線 テスト未知駅 徒歩5分"
        r = analyze_property(base_prop, config)
        assert "テスト未知" in r["missing_stations"]
        assert r["best_teiki"] is None

    def test_non_line_format_ignored(self, base_prop, config):
        """「〇〇線」形式でない路線名は regex にマッチしない"""
        base_prop["station"] = "ゆいレール おもろまち駅 徒歩5分"
        r = analyze_property(base_prop, config)
        # regex requires ○○線 — ゆいレール doesn't match
        assert r["best_station"] is None

    def test_bike_commute_no_teiki(self, base_prop, config):
        config["commute_mode"] = "bike"
        r = analyze_property(base_prop, config)
        # bike 模式不算定期代
        assert r["best_teiki"] is None
        assert r["monthly_total"] == 70000  # rent + mgmt only

    def test_walk_over_max_ignored(self, base_prop, config):
        base_prop["station"] = "御堂筋線 梅田駅 徒歩20分"
        config["max_walk_min"] = 15
        r = analyze_property(base_prop, config)
        assert r["best_station"] is None
