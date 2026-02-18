import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: str) -> str:
    if not value:
        return ""
    return " ".join(value.lower().strip().split())


def normalize_store(value: str) -> str:
    raw = normalize_text(value)
    raw = raw.replace("full h4rd", "fullh4rd")
    return raw.replace(" ", "")


def product_fingerprint(product: Dict) -> str:
    source = normalize_text(product.get("fuente", ""))
    store = normalize_store(product.get("tienda", ""))
    name = normalize_text(product.get("nombre", ""))
    key = f"{source}|{store}|{name}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


class HistoryBackend:
    name = "base"

    def read(self) -> Dict:
        raise NotImplementedError

    def write(self, payload: Dict) -> bool:
        raise NotImplementedError


class LocalJsonHistoryBackend(HistoryBackend):
    name = "local-json"

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def read(self) -> Dict:
        if not self.file_path.exists():
            return {}
        with self.file_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, payload: Dict) -> bool:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.file_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        tmp_path.replace(self.file_path)
        return True


class GithubJsonHistoryBackend(HistoryBackend):
    name = "github-json"

    def __init__(self, repo: str, file_path: str, token: str, branch: str = "main"):
        self.repo = repo
        self.file_path = file_path
        self.token = token
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "price-history-bot",
        }

    def read(self) -> Dict:
        resp = requests.get(
            self.base_url,
            params={"ref": self.branch},
            headers=self._headers(),
            timeout=10,
        )
        if resp.status_code == 404:
            return {}
        resp.raise_for_status()
        data = resp.json()
        encoded = data.get("content", "")
        if not encoded:
            return {}
        raw = base64.b64decode(encoded).decode("utf-8")
        parsed = json.loads(raw)
        parsed["_github_sha"] = data.get("sha")
        return parsed

    def write(self, payload: Dict) -> bool:
        sha = payload.pop("_github_sha", None)
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        body = {
            "message": f"chore: update price history {utc_now_iso()}",
            "content": base64.b64encode(content).decode("utf-8"),
            "branch": self.branch,
        }
        if sha:
            body["sha"] = sha

        resp = requests.put(self.base_url, headers=self._headers(), json=body, timeout=15)
        if resp.status_code in (200, 201):
            return True
        if resp.status_code == 409:
            # Retry once on optimistic lock race.
            latest = self.read()
            latest_sha = latest.get("_github_sha")
            body["sha"] = latest_sha
            resp = requests.put(self.base_url, headers=self._headers(), json=body, timeout=15)
            return resp.status_code in (200, 201)
        return False


class NoOpHistoryBackend(HistoryBackend):
    name = "noop"

    def read(self) -> Dict:
        return {}

    def write(self, payload: Dict) -> bool:
        return False


class PriceHistoryService:
    def __init__(self, backend: HistoryBackend):
        self.backend = backend
        self.max_products = int(os.getenv("PRICE_HISTORY_MAX_PRODUCTS", "1000"))
        self.max_points = int(os.getenv("PRICE_HISTORY_MAX_POINTS", "30"))

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def _base_doc(self) -> Dict:
        return {
            "version": 1,
            "updated_at": None,
            "products": {},
        }

    def _load(self) -> Dict:
        data = self.backend.read() or {}
        if not data:
            return self._base_doc()
        if "products" not in data:
            data["products"] = {}
        return data

    def _prune(self, data: Dict) -> None:
        products = data.get("products", {})
        if len(products) <= self.max_products:
            return
        sorted_items = sorted(
            products.items(),
            key=lambda item: item[1].get("last_seen_at", ""),
            reverse=True,
        )
        keep = dict(sorted_items[: self.max_products])
        data["products"] = keep

    def record_snapshot(self, query: str, products: List[Dict]) -> Dict:
        captured_at = utc_now_iso()
        data = self._load()
        product_map = data["products"]
        changes = {}

        for product in products:
            key = product_fingerprint(product)
            current_price = float(product.get("precio", 0) or 0)
            if current_price <= 0:
                continue

            entry = product_map.setdefault(
                key,
                {
                    "id": key,
                    "nombre": product.get("nombre", ""),
                    "tienda": product.get("tienda", ""),
                    "fuente": product.get("fuente", ""),
                    "link": product.get("link", ""),
                    "imagen": product.get("imagen", ""),
                    "history": [],
                },
            )

            prev_price = entry["history"][-1]["precio"] if entry["history"] else None
            entry["nombre"] = product.get("nombre", entry.get("nombre", ""))
            entry["tienda"] = product.get("tienda", entry.get("tienda", ""))
            entry["fuente"] = product.get("fuente", entry.get("fuente", ""))
            entry["link"] = product.get("link", entry.get("link", ""))
            entry["imagen"] = product.get("imagen", entry.get("imagen", ""))
            entry["last_seen_at"] = captured_at
            entry["history"].append(
                {
                    "captured_at": captured_at,
                    "precio": current_price,
                    "query": query,
                }
            )
            if len(entry["history"]) > self.max_points:
                entry["history"] = entry["history"][-self.max_points :]

            if prev_price is not None:
                delta = round(current_price - prev_price, 2)
                pct = round((delta / prev_price) * 100, 2) if prev_price > 0 else 0.0
            else:
                delta = 0.0
                pct = 0.0

            changes[key] = {
                "previous_price": prev_price,
                "current_price": current_price,
                "delta": delta,
                "delta_pct": pct,
            }

        data["updated_at"] = captured_at
        self._prune(data)
        saved = self.backend.write(data)

        return {
            "saved": saved,
            "captured_at": captured_at,
            "changes": changes,
            "backend": self.backend_name,
        }

    def get_history(self, query: Optional[str] = None, limit: int = 20) -> Dict:
        data = self._load()
        products = list(data.get("products", {}).values())

        if query:
            needle = normalize_text(query)
            products = [
                item
                for item in products
                if needle in normalize_text(item.get("nombre", ""))
                or needle in normalize_store(item.get("tienda", ""))
            ]

        products.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
        trimmed = products[: max(1, min(limit, 100))]
        return {
            "backend": self.backend_name,
            "updated_at": data.get("updated_at"),
            "total": len(trimmed),
            "items": trimmed,
        }


def create_history_service() -> PriceHistoryService:
    backend_kind = os.getenv("PRICE_HISTORY_BACKEND", "").strip().lower()

    if backend_kind == "github":
        token = os.getenv("GITHUB_TOKEN", "")
        repo = os.getenv("GITHUB_REPO", "")
        path = os.getenv("GITHUB_HISTORY_PATH", "data/price_history.json")
        branch = os.getenv("GITHUB_BRANCH", "main")
        if token and repo:
            return PriceHistoryService(
                GithubJsonHistoryBackend(repo=repo, file_path=path, token=token, branch=branch)
            )

    if backend_kind in ("local", ""):
        file_path = os.getenv("PRICE_HISTORY_FILE", "data/price_history.json")
        return PriceHistoryService(LocalJsonHistoryBackend(file_path=file_path))

    return PriceHistoryService(NoOpHistoryBackend())
