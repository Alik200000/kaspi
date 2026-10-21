import csv
import io
from decimal import Decimal
from typing import Dict, Any, Generator, Optional
import openpyxl


class SupplierFeedParser:
    """
    High-performance parser for CSV and Excel supplier feeds.
    Processes data as generator streams to maintain constant O(1) memory usage.
    """

    @staticmethod
    def parse_csv_stream(
        content_stream: io.StringIO,
        column_mapping: Optional[Dict[str, str]] = None,
        delimiter: str = ";"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Parses CSV line by line.
        column_mapping maps file header names to system standard keys:
        {'Артикул': 'supplier_sku', 'Наименование': 'raw_title', 'Цена': 'cost_price', 'Остаток': 'stock_quantity', 'Штрихкод': 'barcode'}
        """
        reader = csv.DictReader(content_stream, delimiter=delimiter)
        mapping = column_mapping or {
            "sku": "supplier_sku",
            "артикул": "supplier_sku",
            "title": "raw_title",
            "наименование": "raw_title",
            "товар": "raw_title",
            "price": "cost_price",
            "цена": "cost_price",
            "stock": "stock_quantity",
            "остаток": "stock_quantity",
            "barcode": "barcode",
            "штрихкод": "barcode",
            "brand": "raw_brand",
            "бренд": "raw_brand"
        }

        # Normalize keys for lookup
        normalized_mapping = {k.lower().strip(): v for k, v in mapping.items()}

        for row in reader:
            parsed_item: Dict[str, Any] = {}
            for col_name, val in row.items():
                if not col_name:
                    continue
                clean_col = col_name.lower().strip()
                target_field = normalized_mapping.get(clean_col)
                if target_field:
                    parsed_item[target_field] = val.strip() if val else None

            if "supplier_sku" in parsed_item and "cost_price" in parsed_item:
                # Clean numerical values
                try:
                    price_str = str(parsed_item["cost_price"]).replace(" ", "").replace(",", ".").replace("₸", "").replace("тг", "")
                    parsed_item["cost_price"] = Decimal(price_str)
                except Exception:
                    continue

                try:
                    stock_str = str(parsed_item.get("stock_quantity", "0")).replace(" ", "").replace(">", "").replace("+", "")
                    parsed_item["stock_quantity"] = int(float(stock_str)) if stock_str else 0
                except Exception:
                    parsed_item["stock_quantity"] = 0

                yield parsed_item

    @staticmethod
    def parse_excel_stream(
        file_bytes: bytes,
        column_mapping: Optional[Dict[str, str]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Parses Excel in read_only mode to prevent high memory usage.
        """
        wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), read_only=True, data_only=True)
        sheet = wb.active
        
        headers = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(cell).strip().lower() if cell is not None else "" for cell in row]
                continue
            
            row_dict = dict(zip(headers, row))
            # Convert row_dict to string dict and reuse CSV mapping logic
            str_dict = {k: str(v) for k, v in row_dict.items() if v is not None}
            
            # Simple conversion
            sku = str_dict.get("артикул") or str_dict.get("sku") or str_dict.get("код")
            price = str_dict.get("цена") or str_dict.get("price") or str_dict.get("стоимость")
            
            if sku and price:
                try:
                    clean_price = str(price).replace(" ", "").replace(",", ".").replace("₸", "")
                    clean_stock = str_dict.get("остаток") or str_dict.get("stock") or "0"
                    
                    yield {
                        "supplier_sku": str(sku).strip(),
                        "raw_title": str(str_dict.get("наименование") or str_dict.get("title") or sku).strip(),
                        "raw_brand": str_dict.get("бренд") or str_dict.get("brand"),
                        "barcode": str_dict.get("штрихкод") or str_dict.get("barcode"),
                        "cost_price": Decimal(clean_price),
                        "stock_quantity": int(float(clean_stock)) if clean_stock else 0
                    }
                except Exception:
                    continue
        wb.close()
