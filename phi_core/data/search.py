from __future__ import annotations

from difflib import SequenceMatcher

from ..models import SearchHit, Song
from .loader import SongCatalog, normalize_key


class SongSearcher:
    def __init__(self, catalog: SongCatalog):
        self.catalog = catalog

    def search(self, query: str, limit: int = 8) -> list[SearchHit]:
        query = query.strip()
        if not query:
            return []
        key = normalize_key(query)
        exact_id = self.catalog.alias_to_id.get(key)
        if exact_id:
            song = self.catalog.songs[exact_id]
            return [SearchHit(song=song, score=1.0, matched=query)]

        hits: dict[str, SearchHit] = {}
        for song in self.catalog.all_songs():
            candidates = [song.id, song.id_with_suffix, song.title, *song.aliases]
            best_score = 0.0
            best_match = ""
            for candidate in candidates:
                candidate_key = normalize_key(candidate)
                if not candidate_key:
                    continue
                if key in candidate_key:
                    score = 0.92 - min(0.2, (len(candidate_key) - len(key)) / 100)
                else:
                    score = SequenceMatcher(None, key, candidate_key).ratio()
                if score > best_score:
                    best_score = score
                    best_match = candidate
            if best_score >= 0.45:
                hits[song.id] = SearchHit(song=song, score=best_score, matched=best_match)

        return sorted(hits.values(), key=lambda hit: (-hit.score, hit.song.title))[:limit]

    def best(self, query: str) -> Song | None:
        hits = self.search(query, limit=1)
        return hits[0].song if hits else None
