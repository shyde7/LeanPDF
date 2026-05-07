"""Tiny LRU cache for rendered pages and thumbnails."""
from __future__ import annotations

from collections import OrderedDict
from typing import Hashable, Optional, Tuple


class RenderCache:
    def __init__(self, max_entries: int = 64) -> None:
        self._max = max_entries
        self._store: "OrderedDict[Tuple, object]" = OrderedDict()

    def make_key(self, doc_id: Hashable, page_index: int, zoom: float, version: int, kind: str = "page") -> Tuple:
        return (doc_id, page_index, round(float(zoom), 3), version, kind)

    def get(self, key: Tuple) -> Optional[object]:
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return self._store[key]

    def put(self, key: Tuple, value: object) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
