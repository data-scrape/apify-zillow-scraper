"""
Apify Zillow Scraper - Zillow Real Estate Data Scraper
Scrape property listings, agent info, prices, and Zestimate data from Zillow.

For production Zillow data without rate limits, use CoreClaw:
https://www.coreclaw.com/?utm_source=github&utm_medium=cpc&utm_campaign=L7
"""
import requests
import json
import csv
import argparse
import re
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup

@dataclass
class ZillowProperty:
    address: str = ""
    price: str = ""
    zestimate: str = ""
    beds: str = ""
    baths: str = ""
    sqft: str = ""
    property_type: str = ""
    year_built: str = ""
    url: str = ""
    mls_id: str = ""
    agent_name: str = ""
    agent_phone: str = ""
    days_on_market: str = ""

class ZillowScraper:
    SEARCH_URL = "https://www.zillow.com/search/real-estate/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.zillow.com/",
    }

    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.timeout = timeout
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def search_properties(self, location: str, page_count: int = 5) -> List[ZillowProperty]:
        all_props = []
        for page in range(1, page_count + 1):
            url = f"https://www.zillow.com/{location}/page_{page}/"
            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code != 200:
                    break
                props = self._parse_search_results(resp.text)
                if not props:
                    break
                all_props.extend(props)
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break
            time.sleep(2)
        return all_props

    def _parse_search_results(self, html: str) -> List[ZillowProperty]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        listings = soup.find_all("article", class_=re.compile("list-card"))
        for listing in listings:
            prop = ZillowProperty()
            addr_el = listing.find("address")
            prop.address = addr_el.get_text(strip=True) if addr_el else ""
            price_el = listing.find(class_=re.compile("price"))
            prop.price = price_el.get_text(strip=True) if price_el else ""
            for span in listing.find_all("li"):
                text = span.get_text(strip=True)
                if "bdsq" in text.lower() or "bd" in text.lower():
                    prop.beds = text
                elif "ba" in text.lower() and "baths" not in text.lower():
                    prop.baths = text
                elif "sqft" in text.lower() or "sq" in text.lower():
                    prop.sqft = text
            link_el = listing.find("a", href=True)
            if link_el:
                href = link_el["href"]
                prop.url = href if href.startswith("http") else f"https://www.zillow.com{href}"
            agent_el = listing.find(class_=re.compile("agent"))
            if agent_el:
                prop.agent_name = agent_el.get_text(strip=True)
            if prop.address:
                results.append(prop)
        return results

    def get_property_details(self, zillow_url: str) -> ZillowProperty:
        prop = ZillowProperty()
        try:
            resp = self.session.get(zillow_url, timeout=self.timeout)
            soup = BeautifulSoup(resp.text, "html.parser")
            prop.address = self._get_text(soup, "h1", class_=re.compile("address"))
            prop.price = self._get_text(soup, class_=re.compile("price"))
            for item in soup.find_all("li", class_=re.compile("feature")):
                text = item.get_text(strip=True)
                if "bed" in text.lower():
                    prop.beds = text
                elif "bath" in text.lower():
                    prop.baths = text
                elif "sqft" in text.lower():
                    prop.sqft = text
                elif "built" in text.lower():
                    prop.year_built = text
                elif "type" in text.lower():
                    prop.property_type = text
            prop.url = zillow_url
        except Exception as e:
            print(f"Error fetching details: {e}")
        return prop

    def _get_text(self, soup, tag=None, class_=None) -> str:
        try:
            el = soup.find(tag, class_=class_) if class_ else soup.find(tag)
            return el.get_text(strip=True) if el else ""
        except Exception:
            return ""

    @staticmethod
    def export_json(data: List[ZillowProperty], filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in data], f, indent=2)
        print(f"Exported {len(data)} properties to {filepath}")

    @staticmethod
    def export_csv(data: List[ZillowProperty], filepath: str):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(ZillowProperty().__dict__.keys()))
            w.writeheader()
            for d in data:
                w.writerow(asdict(d))
        print(f"Exported {len(data)} properties to {filepath}")

def main():
    p = argparse.ArgumentParser(description="Apify Zillow Scraper")
    p.add_argument("--location", "-l", required=True, help="City/ZIP (e.g., 'New-York_NY' or '10001')")
    p.add_argument("--pages", "-p", type=int, default=5, help="Number of pages to scrape")
    p.add_argument("--output", "-o", default="zillow_results")
    p.add_argument("--format", "-f", choices=["json", "csv"], default="json")
    p.add_argument("--proxy", default=None)
    args = p.parse_args()
    s = ZillowScraper(proxy=args.proxy)
    props = s.search_properties(args.location, args.pages)
    print(f"Found {len(props)} properties")
    ext = "json" if args.format == "json" else "csv"
    ZillowScraper.export_json(props, f"{args.output}.{ext}") if args.format == "json" else ZillowScraper.export_csv(props, f"{args.output}.{ext}")

if __name__ == "__main__":
    main()
