# ddcli/cli.py
from __future__ import annotations
import os, json, datetime as dt
from pathlib import Path
import typer
import questionary as q
from rich import print
from rich.table import Table
from ddcli.api import Dojo

def _ask_scan_type_with_dropdown_and_fast_enter(scan_types: list[str]) -> str:
    """
    Show the autocomplete dropdown immediately.
    If the returned value isn't an exact choice, try to resolve it to a single match.
    """
    value = q.autocomplete(
        "Scan type:",
        choices=scan_types,
        match_middle=True
    ).ask()

    if value in scan_types:
        return value

    # If user pressed Enter on a filter string (not exactly a listed choice),
    # resolve it to a unique match (case-insensitive substring).
    typed = (value or "").strip().lower()
    matches = [c for c in scan_types if typed and typed in c.lower()]
    if len(matches) == 1:
        # optional: print a tiny hint so the user sees what got selected
        print(f"[dim]Auto-selected:[/dim] {matches[0]}")
        return matches[0]

    # If multiple (or zero) matches, re-prompt with the filtered list
    if matches:
        return q.autocomplete("Scan type (refine):", choices=matches, match_middle=True).ask()
    else:
        # fallback to full list
        return q.autocomplete("Scan type (choose):", choices=scan_types, match_middle=True).ask()

app = typer.Typer(add_completion=False, help="Import or re-import scans into DefectDojo.")

def _env(var: str, default: str | None = None) -> str | None:
    return os.environ.get(var, default)

def _connect(url: str | None, token: str | None, username: str | None, password: str | None) -> Dojo:
    url = url or _env("DOJO_URL")
    token = token or _env("DOJO_TOKEN")
    username = username or _env("DOJO_USERNAME")
    password = password or _env("DOJO_PASSWORD")
    if not url:
        raise typer.BadParameter("Base URL is required (flag or DOJO_URL).")
    return Dojo(base_url=url, token=token, username=username, password=password)

# -------- scan type loaders ----------
_FALLBACK_SCAN_TYPES = [
    "ZAP Scan", "Trivy Scan", "Checkov Scan", "Dependency Check Scan",
    "Burp Scan", "Snyk Scan", "SonarQube Scan", "Anchore Grype",
]

def _extract_enum_from_spec(spec: dict) -> list[str]:
    # OpenAPI 3 preferred path
    try:
        return list(spec["components"]["schemas"]["ImportScanRequest"]["properties"]["scan_type"]["enum"])
    except Exception:
        pass
    # Swagger 2 fallback path
    try:
        return list(spec["definitions"]["ImportScanRequest"]["properties"]["scan_type"]["enum"])
    except Exception:
        pass
    # Last resort: crawl
    stack = [spec]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "ImportScanRequest" in node and isinstance(node["ImportScanRequest"], dict):
                props = node["ImportScanRequest"].get("properties", {})
                st = props.get("scan_type", {})
                if isinstance(st, dict) and "enum" in st:
                    return list(st["enum"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return []

def load_scan_types_from_spec_file(spec_path: str | None) -> list[str]:
    spec_path = spec_path or _env("DOJO_API_SPEC")
    if not spec_path:
        return []
    p = Path(spec_path)
    if not p.exists():
        print(f"[yellow]Spec not found at {spec_path}.[/yellow]")
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            spec = json.load(f)
        enum_list = _extract_enum_from_spec(spec)
        return _dedup(enum_list)
    except Exception as e:
        print(f"[yellow]Failed to parse local spec ({e}).[/yellow]")
        return []

def _dedup(items: list[str]) -> list[str]:
    seen, out = set(), []
    for s in items or []:
        if isinstance(s, str) and s not in seen:
            seen.add(s); out.append(s)
    return out

def load_scan_types_from_server(dojo: Dojo) -> list[str]:
    """
    Try to fetch OpenAPI JSON from the running DefectDojo instance.
    We intentionally try JSON endpoints only (no YAML, no HTML parsing).
    """
    candidates = [
        f"{dojo.base_url}/api/v2/oa3/openapi.json",
        f"{dojo.base_url}/api/v2/oa3/swagger.json",
        f"{dojo.base_url}/api/v2/oa3/schema/?format=json",
    ]
    for url in candidates:
        try:
            r = dojo.client.get(url, timeout=15.0)
            if r.status_code == 200 and r.headers.get("content-type", "").lower().startswith("application/json"):
                spec = r.json()
                enum_list = _extract_enum_from_spec(spec)
                if enum_list:
                    return _dedup(enum_list)
        except Exception:
            # try next candidate
            continue
    return []

def resolve_scan_types(dojo: Dojo | None, api_spec_path: str | None, source: str) -> list[str]:
    """
    source: 'auto' (server → file → fallback), 'server', or 'file'
    """
    if source == "server":
        if not dojo:
            return []
        st = load_scan_types_from_server(dojo)
        return st or []
    elif source == "file":
        return load_scan_types_from_spec_file(api_spec_path)
    else:  # auto
        if dojo:
            st = load_scan_types_from_server(dojo)
            if st:
                return st
        st = load_scan_types_from_spec_file(api_spec_path)
        return st or []

def _print_summary(res: dict, dojo: Dojo = None):
    t = Table(title="DefectDojo Import Summary", show_lines=False)
    t.add_column("Key"); t.add_column("Value")
    for k in ("test", "engagement", "product_id", "product_type_id", "scan_type", "statistics"):
        if k in res:
            t.add_row(k, str(res[k]))
    
    # Add scan URL if we have test information and dojo instance
    if dojo:
        test_id = None
        # Try different possible response structures
        if "test" in res:
            if isinstance(res["test"], dict) and "id" in res["test"]:
                test_id = res["test"]["id"]
            elif isinstance(res["test"], int):
                test_id = res["test"]
        elif "id" in res:
            test_id = res["id"]
        
        if test_id:
            scan_url = f"{dojo.base_url}/test/{test_id}"
            t.add_row("Scan URL", scan_url)
    
    print(t)

@app.command()
def direct(
    file: str = typer.Option(..., "--file", "-f", exists=True, readable=True, help="Path to scan file"),
    scan_type: str = typer.Option(..., "--scan-type", help="Scanner type as expected by DefectDojo"),
    product: str = typer.Option(None, "--product", help="Product name (if not using IDs)"),
    engagement: str = typer.Option(None, "--engagement", help="Engagement name (used with --product)"),
    engagement_id: int = typer.Option(None, "--engagement-id", help="Engagement ID (creates a new Test)"),
    test_id: int = typer.Option(None, "--test-id", help="Reimport into this Test ID"),
    url: str = typer.Option(None, envvar="DOJO_URL", help="Base URL, e.g. https://dojo.example"),
    token: str = typer.Option(None, envvar="DOJO_TOKEN", help="API Token (preferred)"),
    username: str = typer.Option(None, envvar="DOJO_USERNAME", help="Username (if no token)"),
    password: str = typer.Option(None, envvar="DOJO_PASSWORD", help="Password (if no token)"),
    min_sev: str = typer.Option("Info", "--min-severity"),
    active: bool = typer.Option(None, "--active/--no-active"),
    verified: bool = typer.Option(None, "--verified/--no-verified"),
    auto_create_context: bool = typer.Option(False, help="Let Dojo auto-create Product/Engagement from names"),
    api_spec: str = typer.Option(None, "--api-spec", help="Path to a local OpenAPI JSON file"),
    scan_types_source: str = typer.Option("auto", "--scan-types-source",
                                          help="Where to load scan types: auto | server | file",
                                          metavar="auto|server|file"),
    validate_scan_type: bool = typer.Option(True, "--validate-scan-type/--no-validate-scan-type",
                                            help="Validate --scan-type against schema (server/file)"),
):
    """
    Direct import or reimport without prompts.
    """
    dojo = _connect(url, token, username, password)

    if validate_scan_type:
        allowed = resolve_scan_types(dojo, api_spec, scan_types_source) or _FALLBACK_SCAN_TYPES
        if allowed and scan_type not in allowed:
            raise typer.BadParameter(
                f"Invalid --scan-type '{scan_type}'. Found {len(allowed)} values from {scan_types_source}. "
                f"Try one of: {', '.join(allowed[:12])}..."
            )

    if test_id:
        res = dojo.reimport_scan(test_id=test_id, scan_type=scan_type, file_path=file, minimum_severity=min_sev,
                                 active=active, verified=verified)
        print("[green]Reimport done.[/green]")
    else:
        if engagement_id:
            res = dojo.import_scan(engagement_id=engagement_id, scan_type=scan_type, file_path=file,
                                   minimum_severity=min_sev, active=active, verified=verified)
        else:
            if not (product and engagement):
                raise typer.BadParameter("Provide --engagement-id or both --product and --engagement.")
            res = dojo.import_scan(product_name=product, engagement_name=engagement, scan_type=scan_type,
                                   file_path=file, auto_create_context=auto_create_context,
                                   minimum_severity=min_sev, active=active, verified=verified)
        print("[green]Import done.[/green]")
    _print_summary(res, dojo)

@app.command()
def interactive(
    url: str = typer.Option(None, envvar="DOJO_URL"),
    token: str = typer.Option(None, envvar="DOJO_TOKEN"),
    username: str = typer.Option(None, envvar="DOJO_USERNAME"),
    password: str = typer.Option(None, envvar="DOJO_PASSWORD"),
    api_spec: str = typer.Option(None, "--api-spec", help="Path to a local OpenAPI JSON file"),
    scan_types_source: str = typer.Option("auto", "--scan-types-source",
                                          help="Where to load scan types: auto | server | file",
                                          metavar="auto|server|file"),
):
    """
    Wizard: Product → Engagement → (Reimport) OR (Import).
    Loads full scan types from live Swagger/OpenAPI (or local spec) for accurate autocomplete.
    """
    dojo = _connect(url, token, username, password)

    # ----- Product -----
    query = q.text("Search product (or leave empty to list):").ask()
    products = dojo.list_products(query)
    names = [p.name for p in products]
    choice = q.select("Pick a product or create a new one:", choices=names + ["<Create new product>"]).ask()
    if choice == "<Create new product>":
        new_name = q.text("New product name:").ask()
        product = dojo.create_product(new_name)
    else:
        product = next(p for p in products if p.name == choice)

    # ----- Engagement -----
    engagements = dojo.list_engagements(product.id)
    enames = [e.name or f"Engagement {e.id}" for e in engagements]
    choice_e = q.select("Pick an engagement or create a new one:", choices=enames + ["<Create new engagement>"]).ask()
    if choice_e == "<Create new engagement>":
        title = q.text("Engagement name:").ask()
        today = dt.date.today().isoformat()
        end = q.text(f"End date (YYYY-MM-DD) [{today}]:").ask() or today
        engagement = dojo.create_engagement(product.id, title, today, end, engagement_type="CI/CD")
    else:
        engagement = next(e for e in engagements if (e.name or f"Engagement {e.id}") == choice_e)

    # ----- Test path -----
    mode = q.select("Import mode:", choices=["Re-import into existing Test", "Import (create new Test)"]).ask()
    file_path = q.path("Path to scan file:").ask()

    # Load scan types from server or file
    scan_types = resolve_scan_types(dojo, api_spec, scan_types_source)
    scan_type = _ask_scan_type_with_dropdown_and_fast_enter(scan_types)

    if mode.startswith("Re-import"):
        tests = dojo.list_tests(engagement.id)
        if not tests:
            print("[yellow]No tests found in this engagement; switching to new import.[/yellow]")
            mode = "Import (create new Test)"
        else:
            tchoices = [f"{t.id}: {t.title or 'Test'}" for t in tests]
            tsel = q.select("Select a test:", choices=tchoices).ask()
            test_id = int(tsel.split(":", 1)[0])
            res = dojo.reimport_scan(test_id=test_id, scan_type=scan_type, file_path=file_path)
            print("[green]Reimport done.[/green]")
            _print_summary(res, dojo)
            raise typer.Exit(0)

    res = dojo.import_scan(engagement_id=engagement.id, scan_type=scan_type, file_path=file_path)
    print("[green]Import done.[/green]")
    _print_summary(res, dojo)

if __name__ == "__main__":
    app()
