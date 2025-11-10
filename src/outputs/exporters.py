import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

logger = logging.getLogger(__name__)

class DataExporter:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(
        self,
        records: Iterable[Dict[str, Any]],
        basename: str,
        formats: List[str],
    ) -> None:
        records_list = list(records)
        if not records_list:
            logger.warning("No records provided to exporter; nothing will be written.")
            return

        formats = [fmt.lower() for fmt in formats]
        if "json" in formats:
            self.to_json(records_list, basename)
        if "csv" in formats:
            self.to_csv(records_list, basename)
        if "xlsx" in formats:
            self.to_excel(records_list, basename)

    def to_json(self, records: List[Dict[str, Any]], basename: str) -> Path:
        path = self.output_dir / f"{basename}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        logger.info("Wrote JSON output: %s", path)
        return path

    def to_csv(self, records: List[Dict[str, Any]], basename: str) -> Path:
        path = self.output_dir / f"{basename}.csv"
        if not records:
            logger.warning("No records to write to CSV.")
            return path

        fieldnames = sorted({key for record in records for key in record.keys()})
        df = pd.DataFrame(records, columns=fieldnames)
        df.to_csv(path, index=False)
        logger.info("Wrote CSV output: %s", path)
        return path

    def to_excel(self, records: List[Dict[str, Any]], basename: str) -> Path:
        path = self.output_dir / f"{basename}.xlsx"
        if not records:
            logger.warning("No records to write to Excel.")
            return path

        fieldnames = sorted({key for record in records for key in record.keys()})
        df = pd.DataFrame(records, columns=fieldnames)
        df.to_excel(path, index=False)
        logger.info("Wrote Excel output: %s", path)
        return path