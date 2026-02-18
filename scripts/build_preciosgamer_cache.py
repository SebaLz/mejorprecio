import json
from datetime import datetime, timezone
from pathlib import Path

from scraper import OfertasScraper

TRACKED_QUERIES_FILE = Path('data/tracked_queries.json')
CACHE_FILE = Path('data/preciosgamer_cache.json')


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def normalize_query(query: str) -> str:
    import re
    q = (query or '').lower().strip()
    q = re.sub(r'\s+', ' ', q)
    q = re.sub(r'[^\w\s]', '', q)
    return q.strip()


def dedupe_items(items):
    seen = set()
    out = []
    for item in items:
        key = (
            str(item.get('nombre', '')).strip().lower(),
            str(item.get('link', '')).strip().lower(),
            float(item.get('precio', 0) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def save_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    tracked = load_json(TRACKED_QUERIES_FILE, {'queries': []})
    queries = tracked.get('queries', []) if isinstance(tracked, dict) else []
    queries = [q.strip() for q in queries if isinstance(q, str) and q.strip()]

    existing = load_json(CACHE_FILE, {'generated_at': None, 'queries': {}})
    existing_queries = existing.get('queries', {}) if isinstance(existing, dict) else {}

    scraper = OfertasScraper()
    updated = {
        'generated_at': now_iso(),
        'queries': dict(existing_queries),
    }

    for query in queries:
        key = normalize_query(query)
        print(f'Procesando cache para: {query}')
        try:
            results = scraper.buscar_preciosgamer(query)
            results = dedupe_items(results)
        except Exception as exc:
            print(f'Error con query "{query}": {exc}')
            results = []

        if results:
            updated['queries'][key] = {
                'query': query,
                'updated_at': now_iso(),
                'results': results,
            }
            print(f'  -> {len(results)} resultados guardados')
        else:
            prev = updated['queries'].get(key)
            if prev:
                print('  -> 0 resultados, se conserva cache anterior')
            else:
                updated['queries'][key] = {
                    'query': query,
                    'updated_at': now_iso(),
                    'results': [],
                }
                print('  -> 0 resultados, se crea entrada vacia')

    save_json(CACHE_FILE, updated)
    print(f'Cache generado en {CACHE_FILE}')


if __name__ == '__main__':
    main()
