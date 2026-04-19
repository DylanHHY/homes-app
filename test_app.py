"""app.py Flask API 端點測試"""

import json
import os
import pytest
from app import app, merge_results, load_config, save_config, DEFAULT_CONFIG


@pytest.fixture
def client(tmp_path, monkeypatch):
    """建立測試用 Flask client，使用臨時檔案"""
    import app as app_module

    data_file = str(tmp_path / "data.json")
    config_file = str(tmp_path / "config.json")

    monkeypatch.setattr(app_module, "DATA_FILE", data_file)
    monkeypatch.setattr(app_module, "CONFIG_FILE", config_file)

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def sample_data():
    return [
        {
            "label": "物件A", "url": "https://example.com/a",
            "rent": "6.0万円", "mgmt": "3,000円", "area": "25㎡",
            "station": "御堂筋線 梅田駅 徒歩5分", "floor": "3階/10階建",
            "orientation": "南", "built": "2018年", "layout": "1K 洋室 7帖",
            "movein": "即時", "deposit": "無/無", "position": "",
            "score": 50, "monthly_total": 70000, "within_budget": True,
        },
        {
            "label": "物件B", "url": "https://example.com/b",
            "rent": "7.0万円", "mgmt": "5,000円", "area": "30㎡",
            "station": "中央線 九条駅 徒歩8分", "floor": "8階/12階建",
            "orientation": "東", "built": "2022年", "layout": "1K 洋室 9帖",
            "movein": "即時", "deposit": "1ヶ月/無", "position": "角部屋",
            "score": 80, "monthly_total": 82930, "within_budget": True,
        },
    ]


# ── merge_results ────────────────────────────────

class TestMergeResults:
    def test_no_duplicates(self):
        old = [{"url": "https://a.com", "label": "A", "score": 10, "monthly_total": 50000}]
        new = [{"url": "https://b.com", "label": "B", "score": 20, "monthly_total": 60000}]
        merged = merge_results(old, new)
        assert len(merged) == 2

    def test_dedup_by_url(self):
        old = [{"url": "https://a.com", "label": "old", "score": 10, "monthly_total": 50000}]
        new = [{"url": "https://a.com", "label": "new", "score": 20, "monthly_total": 60000}]
        merged = merge_results(old, new)
        assert len(merged) == 1
        assert merged[0]["label"] == "new"  # 新的覆蓋舊的

    def test_preserves_commute_data(self):
        old = [{"url": "https://a.com", "score": 10, "monthly_total": 50000,
                "commute_min": 25, "commute_route": "test route"}]
        new = [{"url": "https://a.com", "score": 20, "monthly_total": 60000}]
        merged = merge_results(old, new)
        assert merged[0]["commute_min"] == 25
        assert merged[0]["commute_route"] == "test route"

    def test_sorted_by_score_desc(self):
        items = [
            {"url": "https://a.com", "score": 10, "monthly_total": 50000},
            {"url": "https://b.com", "score": 50, "monthly_total": 60000},
            {"url": "https://c.com", "score": 30, "monthly_total": 55000},
        ]
        merged = merge_results([], items)
        assert merged[0]["score"] == 50
        assert merged[1]["score"] == 30
        assert merged[2]["score"] == 10


# ── API: GET / ───────────────────────────────────

class TestIndexRoute:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── API: config ──────────────────────────────────

class TestConfigAPI:
    def test_get_default_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "salary" in data
        assert "scoring" in data
        assert "preferences" in data

    def test_save_and_reload_config(self, client):
        new_config = {**DEFAULT_CONFIG, "salary": 350000, "budget": 120000}
        resp = client.post("/api/config", json=new_config)
        assert resp.status_code == 200

        resp2 = client.get("/api/config")
        data = resp2.get_json()
        assert data["salary"] == 350000
        assert data["budget"] == 120000

    def test_save_config_reanalyzes(self, client, sample_data):
        # 先存入資料
        import app as app_module
        with open(app_module.DATA_FILE, "w") as f:
            json.dump(sample_data, f)

        resp = client.post("/api/config", json=DEFAULT_CONFIG)
        body = resp.get_json()
        assert body["count"] == 2


# ── API: data ────────────────────────────────────

class TestDataAPI:
    def test_get_empty_data(self, client):
        resp = client.get("/api/data")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_get_data_with_content(self, client, sample_data):
        import app as app_module
        with open(app_module.DATA_FILE, "w") as f:
            json.dump(sample_data, f)

        resp = client.get("/api/data")
        data = resp.get_json()
        assert len(data) == 2


# ── API: analyze ─────────────────────────────────

class TestAnalyzeAPI:
    def test_analyze_properties(self, client):
        props = [
            {
                "label": "Test", "url": "https://example.com/test",
                "rent": "5.0万円", "mgmt": "3,000円", "area": "20㎡",
                "station": "御堂筋線 梅田駅 徒歩5分", "floor": "3階/8階建",
                "orientation": "南", "built": "2015年", "layout": "1K",
                "deposit": "無/無",
            }
        ]
        resp = client.post("/api/analyze", json={"properties": props})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) >= 1
        assert data[0]["rent_num"] == 50000


# ── API: delete ──────────────────────────────────

class TestDeleteAPI:
    def test_delete_single(self, client, sample_data):
        import app as app_module
        with open(app_module.DATA_FILE, "w") as f:
            json.dump(sample_data, f)

        resp = client.post("/api/delete", json={"url": "https://example.com/a"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1

        remaining = client.get("/api/data").get_json()
        assert len(remaining) == 1
        assert remaining[0]["url"] == "https://example.com/b"

    def test_delete_batch(self, client, sample_data):
        import app as app_module
        with open(app_module.DATA_FILE, "w") as f:
            json.dump(sample_data, f)

        resp = client.post("/api/delete-batch", json={
            "urls": ["https://example.com/a", "https://example.com/b"]
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 0


# ── API: clear ───────────────────────────────────

class TestClearAPI:
    def test_clear_all(self, client, sample_data):
        import app as app_module
        with open(app_module.DATA_FILE, "w") as f:
            json.dump(sample_data, f)

        resp = client.post("/api/clear")
        assert resp.status_code == 200

        remaining = client.get("/api/data").get_json()
        assert remaining == []


# ── API: scrape (URL 驗證) ───────────────────────

class TestScrapeURLValidation:
    def test_invalid_url_rejected(self, client):
        resp = client.post("/api/scrape", json={"urls": "https://google.com/random"})
        assert resp.status_code == 400

    def test_homes_url_accepted(self, client):
        # 不會真的啟動瀏覽器，只驗證 URL 解析
        resp = client.post("/api/scrape", json={
            "urls": "https://www.homes.co.jp/chintai/b-12345/"
        })
        # 應該回 200 開始抓取（背景執行緒）
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1

    def test_suumo_url_accepted(self, client):
        resp = client.post("/api/scrape", json={
            "urls": "https://suumo.jp/chintai/sc_12345/"
        })
        assert resp.status_code == 200


# ── API: progress ────────────────────────────────

class TestProgressAPI:
    def test_initial_progress(self, client):
        resp = client.get("/api/progress")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "status" in data

    def test_commute_progress(self, client):
        resp = client.get("/api/commute/progress")
        assert resp.status_code == 200

    def test_teiki_progress(self, client):
        resp = client.get("/api/teiki/progress")
        assert resp.status_code == 200
