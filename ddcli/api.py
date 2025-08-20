from __future__ import annotations
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel

# Simple models to make callsites clean.
class Product(BaseModel):
    id: int
    name: str

class Engagement(BaseModel):
    id: int
    name: Optional[str] = None
    product: int

class Test(BaseModel):
    id: int
    title: Optional[str] = None
    engagement: int

class Dojo:
    def __init__(self, base_url: str, token: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=timeout)
        if token:
            self.client.headers["Authorization"] = f"Token {token}"
        elif username and password:
            # /api/v2/api-token-auth/
            r = self.client.post(f"{self.base_url}/api/v2/api-token-auth/", data={"username": username, "password": password})
            r.raise_for_status()
            tok = r.json().get("token")
            self.client.headers["Authorization"] = f"Token {tok}"

    # ----- Products -----
    def list_products(self, name_query: Optional[str] = None, limit: int = 100) -> List[Product]:
        params: Dict[str, Any] = {"limit": limit}
        if name_query:
            params["name"] = name_query  # server-side filter; fallback to client filter below if server ignores it
        r = self.client.get(f"{self.base_url}/api/v2/products/", params=params)
        r.raise_for_status()
        items = r.json().get("results", r.json())
        prods = [Product(**p) for p in items if isinstance(p, dict)]
        if name_query:
            # client-side contains filter just in case
            prods = [p for p in prods if name_query.lower() in p.name.lower()]
        return prods

    def create_product(self, name: str) -> Product:
        r = self.client.post(f"{self.base_url}/api/v2/products/", json={"name": name})
        r.raise_for_status()
        return Product(**r.json())

    # ----- Engagements -----
    def list_engagements(self, product_id: int, limit: int = 100) -> List[Engagement]:
        r = self.client.get(f"{self.base_url}/api/v2/engagements/", params={"product": product_id, "limit": limit})
        r.raise_for_status()
        items = r.json().get("results", r.json())
        return [Engagement(**e) for e in items if isinstance(e, dict)]

    def create_engagement(self, product_id: int, name: str, start_date: str, end_date: str, engagement_type: str = "CI/CD") -> Engagement:
        payload = {
            "product": product_id,
            "name": name,
            "target_start": start_date,  # YYYY-MM-DD
            "target_end": end_date,      # YYYY-MM-DD
            "engagement_type": engagement_type,  # e.g. "CI/CD" or "Interactive"
            "status": "In Progress",
        }
        r = self.client.post(f"{self.base_url}/api/v2/engagements/", json=payload)
        r.raise_for_status()
        return Engagement(**r.json())

    # ----- Tests -----
    def list_tests(self, engagement_id: int, limit: int = 100) -> List[Test]:
        r = self.client.get(f"{self.base_url}/api/v2/tests/", params={"engagement": engagement_id, "limit": limit})
        r.raise_for_status()
        items = r.json().get("results", r.json())
        return [Test(**t) for t in items if isinstance(t, dict)]

    # (Optional) create a test explicitly if you don’t want import-scan to create it.
    def create_test(self, engagement_id: int, test_type_id: int, title: str, start_date: str, end_date: str) -> Test:
        payload = {
            "engagement": engagement_id,
            "test_type": test_type_id,
            "title": title,
            "target_start": start_date,
            "target_end": end_date,
        }
        r = self.client.post(f"{self.base_url}/api/v2/tests/", json=payload)
        r.raise_for_status()
        return Test(**r.json())

    # ----- Import / Reimport -----
    def import_scan(self, *, engagement_id: Optional[int] = None, product_name: Optional[str] = None,
                    engagement_name: Optional[str] = None, scan_type: str, file_path: str,
                    auto_create_context: bool = False, deduplication_on_engagement: Optional[bool] = None,
                    test_title: Optional[str] = None, minimum_severity: str = "Info",
                    active: Optional[bool] = None, verified: Optional[bool] = None):
        # /api/v2/import-scan/ (multipart/form-data)
        data: Dict[str, Any] = {"scan_type": scan_type, "minimum_severity": minimum_severity}
        if engagement_id:
            data["engagement"] = str(engagement_id)
        if product_name:
            data["product_name"] = product_name
        if engagement_name:
            data["engagement_name"] = engagement_name
        if auto_create_context:
            data["auto_create_context"] = "true"
        if deduplication_on_engagement is not None:
            data["deduplication_on_engagement"] = "true" if deduplication_on_engagement else "false"
        if test_title:
            data["test_title"] = test_title
        if active is not None:
            data["active"] = "true" if active else "false"
        if verified is not None:
            data["verified"] = "true" if verified else "false"

        with open(file_path, "rb") as f:
            files = {"file": (file_path, f)}
            r = self.client.post(f"{self.base_url}/api/v2/import-scan/", data=data, files=files)
        r.raise_for_status()
        return r.json()

    def reimport_scan(self, *, test_id: int, scan_type: str, file_path: str,
                      minimum_severity: str = "Info", active: Optional[bool] = None, verified: Optional[bool] = None):
        data: Dict[str, Any] = {"scan_type": scan_type, "test": str(test_id), "minimum_severity": minimum_severity}
        if active is not None:
            data["active"] = "true" if active else "false"
        if verified is not None:
            data["verified"] = "true" if verified else "false"
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f)}
            r = self.client.post(f"{self.base_url}/api/v2/reimport-scan/", data=data, files=files)
        r.raise_for_status()
        return r.json()
