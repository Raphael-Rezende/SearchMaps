from pathlib import Path
import sys
from typing import Callable, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
SEARCH_DIR = BASE_DIR / "Search"

if str(SEARCH_DIR) not in sys.path:
    sys.path.insert(0, str(SEARCH_DIR))

import searcher  # noqa: E402


def run_search(
    city: str,
    query: str,
    limit: Optional[int] = None,
    progress_cb: Optional[Callable[[int, Optional[int]], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> List[Dict[str, str]]:
    return searcher.buscar_estabelecimentos(
        city,
        query,
        limit=limit,
        progress_cb=progress_cb,
        should_cancel=should_cancel,
        return_dicts=True,
    )
