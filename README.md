# Homes App

A web-based rental property analyzer for Japan. Scrape listings from [HOMES.co.jp](https://www.homes.co.jp/chintai/) and [SUUMO.jp](https://suumo.jp/chintai/), then automatically score and compare them based on your personal criteria.

## Features

- **Multi-site scraping** - Supports HOMES.co.jp and SUUMO.jp listing URLs
- **Auto scoring** - Configurable scoring weights (corner unit, floor, orientation, age, budget, etc.)
- **Commute analysis** - Google Maps door-to-door commute time lookup with multiple transport modes (train, car, bike, walk) and automatic fallback
- **Commuter pass** - Auto-calculate monthly train pass cost (teiki) via NAVITIME
- **Initial cost breakdown** - Deposit, key money, guarantor, agency fee, insurance estimates
- **Multi-language** - UI in Traditional Chinese, Japanese, and English
- **Onboarding wizard** - Step-by-step setup for new users
- **Japan-wide** - Searchable city selector covering 50+ cities across all regions

## Screenshots

> TODO

## Requirements

- Python 3.10+
- Google Chrome (for scraping via Playwright)

## Setup

```bash
# Install dependencies
pip install flask beautifulsoup4 playwright
playwright install chromium

# Run
python app.py
```

Open http://localhost:5050 in your browser.

## Usage

1. **First launch** - Complete the onboarding wizard (language, location, budget, preferences)
2. **Find listings** - Browse [HOMES.co.jp](https://www.homes.co.jp/chintai/) or [SUUMO.jp](https://suumo.jp/chintai/)
3. **Paste URLs** - Copy listing URLs into the text box and click "Analyze"
4. **Compare** - Sort by score, rent, area, age, or commute time
5. **Check commute** - Click "Check Commute" to auto-lookup door-to-door times via Google Maps
6. **View details** - Click any listing name to see the full breakdown

## Configuration

All settings are stored in `config.json` (auto-created, gitignored). Key fields:

| Field | Description |
|-------|-------------|
| `city_label` | City name for search context |
| `office_label` | Nearest station to workplace |
| `office_address` | Full workplace address (for Google Maps) |
| `commute_mode` | `train` / `walk` / `bike` / `car` |
| `salary` | Monthly take-home pay (JPY) |
| `fixed_expenses` | Fixed monthly expenses excluding rent |
| `scoring` | Weight values for each scoring criterion |
| `preferences` | Min floor, area, room size, orientation |

## Tech Stack

- **Backend**: Flask (Python)
- **Frontend**: Vanilla JS + Jinja2 templates
- **Scraping**: Playwright + BeautifulSoup4
- **Data**: JSON file storage

## License

MIT
