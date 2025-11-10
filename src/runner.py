import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from extractors.listings_parser import ListingScraper
from outputs.exporters import DataExporter

DEFAULT_SETTINGS = {
    "base_url": "https://www.bizbuysell.com",
    "user_agent": "BizBuySellScraper/1.0 (+https://bitbash.dev)",
    "request_timeout": 20,
    "concurrency": 5,
    "delay_between_requests": 1.0,
    "output_directory": "data",
    "output_formats": ["json", "csv", "xlsx"],
    "input_file": "data/inputs.sample.txt",
    "log_level": "INFO",
}

def load_settings(config_path: Optional[str]) -> Dict[str, Any]:
    settings: Dict[str, Any] = DEFAULT_SETTINGS.copy()

    if config_path:
        path = Path(config_path)
    else:
        # Default to the example settings path relative to this file
        path = Path(__file__).resolve().parent / "config" / "settings.example.json"

    if path.is_file():
        try:
            with path.open("r", encoding="utf-8") as f:
                file_settings = json.load(f)
            settings.update(file_settings)
        except Exception as exc:
            print(f"Warning: failed to load settings from {path}: {exc}")
    else:
        print(f"Warning: settings file {path} not found, using built-in defaults.")

    return settings

def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def read_input_urls(path: str) -> List[str]:
    file_path = Path(path)
    if not file_path.is_file():
        logging.error("Input file %s does not exist.", file_path)
        raise FileNotFoundError(f"Input file {file_path} not found")

    urls: List[str] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)

    if not urls:
        logging.warning("No URLs found in %s", file_path)

    return urls

def scrape_urls(
    scraper: ListingScraper,
    urls: List[str],
    concurrency: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    if not urls:
        logging.info("No URLs to scrape.")
        return results

    concurrency = max(1, min(concurrency, len(urls)))

    logging.info("Starting scrape for %d URL(s) with concurrency=%d", len(urls), concurrency)

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_url = {
            executor.submit(scraper.scrape_listing, url): url for url in urls
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
                    logging.info("Scraped listing: %s", url)
                else:
                    logging.warning("No data extracted from: %s", url)
            except Exception as exc:
                logging.exception("Error scraping %s: %s", url, exc)

    logging.info("Finished scraping. Successfully scraped %d of %d URL(s).", len(results), len(urls))
    return results

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="BizBuySell Listings Scraper runner",
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Path to settings JSON file (default: src/config/settings.example.json)",
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to input URLs file (overrides value from settings)",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        help="Output directory (overrides value from settings)",
    )
    parser.add_argument(
        "--formats",
        "-f",
        nargs="+",
        choices=["json", "csv", "xlsx"],
        help="Output formats to generate (overrides value from settings)",
    )

    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    configure_logging(settings.get("log_level", "INFO"))

    input_file = args.input or settings.get("input_file", DEFAULT_SETTINGS["input_file"])
    output_dir = args.output_dir or settings.get(
        "output_directory", DEFAULT_SETTINGS["output_directory"]
    )
    output_formats = args.formats or settings.get(
        "output_formats", DEFAULT_SETTINGS["output_formats"]
    )
    concurrency = int(settings.get("concurrency", DEFAULT_SETTINGS["concurrency"]))

    logging.info("Using input file: %s", input_file)
    logging.info("Using output dir: %s", output_dir)
    logging.info("Using output formats: %s", ", ".join(output_formats))

    urls = read_input_urls(input_file)
    if not urls:
        logging.error("No URLs available to scrape. Exiting.")
        return

    scraper = ListingScraper(
        base_url=settings.get("base_url", DEFAULT_SETTINGS["base_url"]),
        user_agent=settings.get("user_agent", DEFAULT_SETTINGS["user_agent"]),
        timeout=int(settings.get("request_timeout", DEFAULT_SETTINGS["request_timeout"])),
        delay_between_requests=float(
            settings.get(
                "delay_between_requests",
                DEFAULT_SETTINGS["delay_between_requests"],
            )
        ),
    )

    data = scrape_urls(scraper, urls, concurrency=concurrency)
    if not data:
        logging.error("No listing data scraped. Nothing to export.")
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    basename = f"bizbuysell_listings_{timestamp}"

    exporter = DataExporter(output_dir)
    try:
        exporter.export_all(data, basename, output_formats)
    except Exception as exc:
        logging.exception("Failed to export data: %s", exc)
        return

    logging.info("Scraping and export completed successfully.")

if __name__ == "__main__":
    main()