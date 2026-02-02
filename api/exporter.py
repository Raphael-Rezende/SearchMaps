from pathlib import Path
import sys
from typing import List, Dict, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
SEARCH_DIR = BASE_DIR / "Search"
EXPORT_DIR = BASE_DIR / "exports"

if str(SEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(SEARCH_DIR))

from utils import exportar_lista_para_excel, exportar_lista_para_csv  # noqa: E402

COLUMNS = [
    "city",
    "query",
    "name",
    "address",
    "delivery",
    "phone",
    "menu",
    "website",
    "maps_url",
]


def export_results(results: List[Dict[str, str]], job_id: str, fmt: str) -> Tuple[str, Path]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"searchmaps_{job_id}.{fmt}"
    path = EXPORT_DIR / filename

    if fmt == "xlsx":
        exportar_lista_para_excel(results, path, colunas=COLUMNS)
    elif fmt == "csv":
        exportar_lista_para_csv(results, path, colunas=COLUMNS)
    else:
        raise ValueError("Formato de exportação inválido.")

    return filename, path
