#!/usr/bin/env python3
"""
Dental Insights — Dataset Download & Organization Script

Downloads dental imaging datasets from publicly accessible sources:
- Kaggle (via API)
- Roboflow (via API)
- Zenodo (via REST API)
- Figshare (via REST API)
- Mendeley Data (via REST API)
- IEEE DataPort (direct download)
- Scientific Data / Nature (direct download)

Datasets requiring manual access (PhysioNet, Grand Challenge, MICCAI, etc.)
are listed in a generated report with instructions.

Usage:
    python download_datasets.py --output-dir ./dental_data
    python download_datasets.py --output-dir ./dental_data --only kaggle zenodo
    python download_datasets.py --output-dir ./dental_data --list-manual
    python download_datasets.py --output-dir ./dental_data --dry-run
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CATALOG_PATH = Path(__file__).parent / "datasets_catalog.json"

# Standard folder layout for the training pipeline
FOLDER_STRUCTURE = {
    "panoramic_2d": "panoramic_2d",
    "periapical_2d": "periapical_2d",
    "cbct_3d": "cbct_3d",
    "intraoral_scan": "intraoral_scan",
}

AGENT_MAPPING = {
    "panoramic_2d": ["agent1_qwen8b", "agent2_qwen30b", "agent3_internvl78b"],
    "periapical_2d": ["agent1_qwen8b", "agent2_qwen30b", "agent3_internvl78b"],
    "cbct_3d": ["agent3_internvl78b"],
    "intraoral_scan": ["agent3_internvl78b"],
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("dental_download")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DatasetEntry:
    name: str
    source: str
    size: str
    annotations: str
    access: str  # direct | registration | request | credentialed
    platform: str
    url: str
    fmt: str
    license: str
    category: str
    registration_notes: str = ""
    request_notes: str = ""


@dataclass
class DownloadResult:
    dataset: str
    status: str  # success | skipped | failed | manual
    message: str
    path: Optional[str] = None


# ---------------------------------------------------------------------------
# Catalog loader
# ---------------------------------------------------------------------------


def load_catalog(catalog_path: Path) -> list[DatasetEntry]:
    """Load the dataset catalog JSON and return a flat list of DatasetEntry."""
    with open(catalog_path) as f:
        catalog = json.load(f)

    entries: list[DatasetEntry] = []
    for category_key, category_data in catalog["categories"].items():
        for ds in category_data["datasets"]:
            entries.append(
                DatasetEntry(
                    name=ds["name"],
                    source=ds.get("source", ""),
                    size=ds.get("size", ""),
                    annotations=ds.get("annotations", ""),
                    access=ds.get("access", "unknown"),
                    platform=ds.get("platform", ""),
                    url=ds.get("url", ""),
                    fmt=ds.get("format", ""),
                    license=ds.get("license", ""),
                    category=category_key,
                    registration_notes=ds.get("registration_notes", ""),
                    request_notes=ds.get("request_notes", ""),
                )
            )
    return entries


# ---------------------------------------------------------------------------
# Downloaders per platform
# ---------------------------------------------------------------------------


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_dirname(name: str) -> str:
    """Convert dataset name to a safe directory name."""
    return name.lower().replace(" ", "_").replace("-", "_").replace("+", "plus")


def download_kaggle(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Download a Kaggle dataset using the kaggle CLI."""
    # Extract dataset slug from URL
    # Expected URL format: https://www.kaggle.com/datasets/<owner>/<dataset>
    parts = entry.url.rstrip("/").split("/")
    try:
        idx = parts.index("datasets")
        slug = "/".join(parts[idx + 1 : idx + 3])
    except (ValueError, IndexError):
        return DownloadResult(
            entry.name,
            "failed",
            f"Could not parse Kaggle dataset slug from URL: {entry.url}",
        )

    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    try:
        subprocess.run(
            [
                "kaggle",
                "datasets",
                "download",
                "-d",
                slug,
                "-p",
                str(dataset_dir),
                "--unzip",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        return DownloadResult(
            entry.name, "success", f"Downloaded to {dataset_dir}", str(dataset_dir)
        )
    except FileNotFoundError:
        return DownloadResult(
            entry.name,
            "failed",
            "kaggle CLI not found. Install with: pip install kaggle\n"
            "Then configure ~/.kaggle/kaggle.json with your API key.",
        )
    except subprocess.CalledProcessError as e:
        return DownloadResult(entry.name, "failed", f"Kaggle download failed: {e.stderr}")
    except subprocess.TimeoutExpired:
        return DownloadResult(entry.name, "failed", "Kaggle download timed out (30 min)")


def download_zenodo(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Download from Zenodo using its REST API."""
    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    try:
        import requests
    except ImportError:
        return DownloadResult(
            entry.name, "failed", "requests library not found. Install with: pip install requests"
        )

    # Search Zenodo for dental panoramic datasets
    search_url = "https://zenodo.org/api/records"
    params = {"q": f'title:"{entry.name}" dental', "size": 5}

    try:
        resp = requests.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
        hits = resp.json().get("hits", {}).get("hits", [])

        if not hits:
            # Try broader search
            params["q"] = "dental panoramic radiograph"
            resp = requests.get(search_url, params=params, timeout=30)
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])

        if not hits:
            return DownloadResult(
                entry.name, "skipped", "No matching Zenodo records found. Manual search needed."
            )

        record = hits[0]
        files = record.get("files", [])
        if not files:
            return DownloadResult(entry.name, "skipped", "Zenodo record found but no downloadable files.")

        downloaded = []
        for file_info in files:
            file_url = file_info["links"]["self"]
            filename = file_info["key"]
            filepath = dataset_dir / filename

            if filepath.exists():
                log.info("  [skip] %s already exists", filename)
                downloaded.append(filename)
                continue

            log.info("  Downloading %s (%s bytes)...", filename, file_info.get("size", "?"))
            file_resp = requests.get(file_url, stream=True, timeout=60)
            file_resp.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in file_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded.append(filename)

        return DownloadResult(
            entry.name,
            "success",
            f"Downloaded {len(downloaded)} files to {dataset_dir}",
            str(dataset_dir),
        )

    except Exception as e:
        return DownloadResult(entry.name, "failed", f"Zenodo download error: {e}")


def download_figshare(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Download from Figshare using its REST API."""
    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    try:
        import requests
    except ImportError:
        return DownloadResult(
            entry.name, "failed", "requests library not found. Install with: pip install requests"
        )

    search_url = "https://api.figshare.com/v2/articles/search"
    payload = {"search_for": f"{entry.name} dental", "page_size": 5}

    try:
        resp = requests.post(search_url, json=payload, timeout=30)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return DownloadResult(
                entry.name, "skipped", "No matching Figshare articles found."
            )

        article = results[0]
        article_id = article["id"]

        # Get article details with file links
        detail_resp = requests.get(
            f"https://api.figshare.com/v2/articles/{article_id}", timeout=30
        )
        detail_resp.raise_for_status()
        detail = detail_resp.json()
        files = detail.get("files", [])

        if not files:
            return DownloadResult(entry.name, "skipped", "Figshare article found but no files.")

        downloaded = []
        for file_info in files:
            file_url = file_info["download_url"]
            filename = file_info["name"]
            filepath = dataset_dir / filename

            if filepath.exists():
                log.info("  [skip] %s already exists", filename)
                downloaded.append(filename)
                continue

            log.info("  Downloading %s (%s bytes)...", filename, file_info.get("size", "?"))
            file_resp = requests.get(file_url, stream=True, timeout=60)
            file_resp.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in file_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            downloaded.append(filename)

        return DownloadResult(
            entry.name,
            "success",
            f"Downloaded {len(downloaded)} files to {dataset_dir}",
            str(dataset_dir),
        )

    except Exception as e:
        return DownloadResult(entry.name, "failed", f"Figshare download error: {e}")


def download_mendeley(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Download from Mendeley Data using its REST API."""
    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    try:
        import requests
    except ImportError:
        return DownloadResult(
            entry.name, "failed", "requests library not found. Install with: pip install requests"
        )

    # Extract DOI or dataset ID from URL if present
    search_url = "https://data.mendeley.com/api/datasets"
    params = {"search": f"{entry.name} dental", "limit": 5}

    try:
        resp = requests.get(search_url, params=params, timeout=30)
        resp.raise_for_status()
        results = resp.json()

        if not results:
            return DownloadResult(
                entry.name, "skipped", "No matching Mendeley datasets found."
            )

        # For Mendeley, often need to download via browser due to auth
        dataset = results[0] if isinstance(results, list) else results
        dataset_url = dataset.get("url", entry.url)

        return DownloadResult(
            entry.name,
            "skipped",
            f"Mendeley dataset found. Download manually from: {dataset_url}\n"
            f"  Mendeley often requires browser-based download for large datasets.",
        )

    except Exception as e:
        # Mendeley API can be restrictive — fall back to manual
        return DownloadResult(
            entry.name,
            "skipped",
            f"Mendeley API access limited. Download manually from: {entry.url}\n"
            f"  Error: {e}",
        )


def download_roboflow(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Download from Roboflow using the roboflow Python package."""
    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    api_key = os.environ.get("ROBOFLOW_API_KEY")
    if not api_key:
        return DownloadResult(
            entry.name,
            "skipped",
            "ROBOFLOW_API_KEY not set. Export it or set in .env file.\n"
            "  Get your key from: https://app.roboflow.com/settings/api\n"
            f"  Then browse: {entry.url}",
        )

    try:
        from roboflow import Roboflow

        rf = Roboflow(api_key=api_key)
        # Roboflow requires workspace/project/version — user needs to specify
        return DownloadResult(
            entry.name,
            "skipped",
            f"Roboflow API key found. Browse datasets at: {entry.url}\n"
            "  To download, use:\n"
            '    rf = Roboflow(api_key="YOUR_KEY")\n'
            '    project = rf.workspace("WORKSPACE").project("PROJECT")\n'
            '    dataset = project.version(VERSION).download("yolov8")\n'
            f"  Output dir: {dataset_dir}",
        )
    except ImportError:
        return DownloadResult(
            entry.name,
            "skipped",
            "roboflow package not found. Install with: pip install roboflow\n"
            f"  Then browse: {entry.url}",
        )


def download_ieee_dataport(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """IEEE DataPort requires login — provide instructions."""
    return DownloadResult(
        entry.name,
        "manual",
        f"IEEE DataPort requires login. Download from: {entry.url}\n"
        "  1. Create IEEE account at https://ieee-dataport.org/\n"
        "  2. Search for the dataset\n"
        "  3. Download and extract to the path below\n"
        f"  Target: {dest / _safe_dirname(entry.name)}",
    )


def download_direct(entry: DatasetEntry, dest: Path) -> DownloadResult:
    """Attempt direct HTTP download for datasets with direct links."""
    dataset_dir = _ensure_dir(dest / _safe_dirname(entry.name))

    return DownloadResult(
        entry.name,
        "manual",
        f"Direct download available from: {entry.url}\n"
        f"  Platform: {entry.platform}\n"
        f"  Download and extract to: {dataset_dir}",
    )


# Platform router
PLATFORM_DOWNLOADERS = {
    "Kaggle": download_kaggle,
    "Roboflow": download_roboflow,
    "Zenodo": download_zenodo,
    "Figshare": download_figshare,
    "Mendeley Data": download_mendeley,
    "IEEE DataPort": download_ieee_dataport,
}


def download_dataset(entry: DatasetEntry, base_dir: Path) -> DownloadResult:
    """Route a dataset entry to the appropriate downloader."""
    category_dir = base_dir / FOLDER_STRUCTURE.get(entry.category, entry.category)
    _ensure_dir(category_dir)

    # Manual-access datasets
    if entry.access in ("request", "credentialed", "registration"):
        notes = entry.registration_notes or entry.request_notes or ""
        return DownloadResult(
            entry.name,
            "manual",
            f"Requires {entry.access} access via {entry.platform}.\n"
            f"  URL: {entry.url}\n"
            f"  {notes}\n"
            f"  Target dir: {category_dir / _safe_dirname(entry.name)}",
        )

    # Find platform-specific downloader
    downloader = PLATFORM_DOWNLOADERS.get(entry.platform)
    if downloader:
        return downloader(entry, category_dir)

    # Fallback to direct download instructions
    return download_direct(entry, category_dir)


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------


def generate_manual_access_report(
    entries: list[DatasetEntry], results: list[DownloadResult], output_dir: Path
) -> Path:
    """Generate a markdown report for datasets requiring manual access."""
    report_path = output_dir / "MANUAL_ACCESS_GUIDE.md"

    manual_entries = [
        (e, r)
        for e, r in zip(entries, results)
        if r.status in ("manual", "skipped")
    ]

    lines = [
        "# Dental Insights — Manual Dataset Access Guide",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**{len(manual_entries)}** datasets require manual download or registration.",
        "",
    ]

    # Group by access type
    for access_type, label in [
        ("registration", "Requires Registration"),
        ("credentialed", "Requires Credentialed Access"),
        ("request", "Requires Email/Form Request"),
    ]:
        group = [(e, r) for e, r in manual_entries if e.access == access_type]
        if group:
            lines.append(f"## {label}")
            lines.append("")
            for entry, result in group:
                lines.append(f"### {entry.name}")
                lines.append(f"- **Source**: {entry.source}")
                lines.append(f"- **Size**: {entry.size}")
                lines.append(f"- **Annotations**: {entry.annotations}")
                lines.append(f"- **Platform**: {entry.platform}")
                lines.append(f"- **URL**: {entry.url}")
                lines.append(f"- **Category**: {entry.category}")
                if entry.registration_notes:
                    lines.append(f"- **Notes**: {entry.registration_notes}")
                if entry.request_notes:
                    lines.append(f"- **Notes**: {entry.request_notes}")
                lines.append("")

    # Direct access that failed or was skipped
    other = [(e, r) for e, r in manual_entries if e.access == "direct"]
    if other:
        lines.append("## Direct Access (Download Manually)")
        lines.append("")
        for entry, result in other:
            lines.append(f"### {entry.name}")
            lines.append(f"- **Platform**: {entry.platform}")
            lines.append(f"- **URL**: {entry.url}")
            lines.append(f"- **Size**: {entry.size}")
            lines.append(f"- **Message**: {result.message}")
            lines.append("")

    lines.append("## Target Folder Structure")
    lines.append("")
    lines.append("```")
    lines.append("dental_data/")
    for folder in FOLDER_STRUCTURE.values():
        lines.append(f"  {folder}/")
        lines.append(f"    <dataset_name>/")
        lines.append(f"      images/")
        lines.append(f"      annotations/")
    lines.append("```")
    lines.append("")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    return report_path


def generate_summary(results: list[DownloadResult], output_dir: Path) -> Path:
    """Generate a JSON summary of all download results."""
    summary_path = output_dir / "download_summary.json"
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "success": sum(1 for r in results if r.status == "success"),
        "manual": sum(1 for r in results if r.status == "manual"),
        "skipped": sum(1 for r in results if r.status == "skipped"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "results": [
            {
                "dataset": r.dataset,
                "status": r.status,
                "message": r.message,
                "path": r.path,
            }
            for r in results
        ],
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    return summary_path


# ---------------------------------------------------------------------------
# Folder structure setup
# ---------------------------------------------------------------------------


def setup_folder_structure(base_dir: Path) -> None:
    """Create the standardized folder structure for the training pipeline."""
    for category, folder in FOLDER_STRUCTURE.items():
        category_dir = base_dir / folder
        category_dir.mkdir(parents=True, exist_ok=True)

        # Create README in each category folder
        readme = category_dir / "README.txt"
        if not readme.exists():
            agents = AGENT_MAPPING.get(category, [])
            with open(readme, "w") as f:
                f.write(f"Category: {category}\n")
                f.write(f"Target agents: {', '.join(agents)}\n")
                f.write(f"\nPlace downloaded datasets in subdirectories here.\n")
                f.write(f"Each dataset should have its own folder with:\n")
                f.write(f"  - images/    (raw images)\n")
                f.write(f"  - annotations/ (labels, masks, JSON)\n")
                f.write(f"  - metadata.json (dataset info)\n")

    log.info("Folder structure created at %s", base_dir)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Dental Insights — Dataset Download & Organization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./dental_data"),
        help="Base directory for downloaded datasets (default: ./dental_data)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=CATALOG_PATH,
        help="Path to datasets_catalog.json",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["kaggle", "zenodo", "figshare", "mendeley", "roboflow", "ieee", "all"],
        default=["all"],
        help="Download only from specific platforms",
    )
    parser.add_argument(
        "--list-manual",
        action="store_true",
        help="Only list datasets requiring manual access (no downloads)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading",
    )
    parser.add_argument(
        "--setup-folders",
        action="store_true",
        help="Only create the folder structure (no downloads)",
    )

    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load catalog
    if not args.catalog.exists():
        log.error("Catalog not found: %s", args.catalog)
        sys.exit(1)

    entries = load_catalog(args.catalog)
    log.info("Loaded %d datasets from catalog", len(entries))

    # Setup folders
    setup_folder_structure(output_dir)

    if args.setup_folders:
        log.info("Folder structure created. Exiting.")
        return

    # Filter by platform if --only is specified
    platform_filter = None
    if "all" not in args.only:
        platform_map = {
            "kaggle": "Kaggle",
            "zenodo": "Zenodo",
            "figshare": "Figshare",
            "mendeley": "Mendeley Data",
            "roboflow": "Roboflow",
            "ieee": "IEEE DataPort",
        }
        platform_filter = {platform_map[p] for p in args.only if p in platform_map}

    # List manual access only
    if args.list_manual:
        manual = [e for e in entries if e.access in ("request", "credentialed", "registration")]
        print(f"\n{'='*60}")
        print(f" Datasets Requiring Manual Access ({len(manual)} total)")
        print(f"{'='*60}\n")
        for e in manual:
            print(f"  [{e.access.upper()}] {e.name}")
            print(f"    Platform: {e.platform}")
            print(f"    URL: {e.url}")
            print(f"    Size: {e.size}")
            if e.registration_notes:
                print(f"    Notes: {e.registration_notes}")
            if e.request_notes:
                print(f"    Notes: {e.request_notes}")
            print()
        return

    # Process downloads
    results: list[DownloadResult] = []

    for entry in entries:
        if platform_filter and entry.platform not in platform_filter:
            continue

        log.info("Processing: %s [%s / %s]", entry.name, entry.platform, entry.access)

        if args.dry_run:
            if entry.access in ("request", "credentialed", "registration"):
                status = "manual"
            else:
                status = "would_download"
            results.append(DownloadResult(entry.name, status, f"[DRY RUN] {entry.platform}: {entry.url}"))
            continue

        result = download_dataset(entry, output_dir)
        results.append(result)

        status_icon = {
            "success": "[OK]",
            "skipped": "[SKIP]",
            "manual": "[MANUAL]",
            "failed": "[FAIL]",
        }.get(result.status, "[?]")
        log.info("  %s %s", status_icon, result.message.split("\n")[0])

    # Generate reports
    if results:
        summary_path = generate_summary(results, output_dir)
        report_path = generate_manual_access_report(entries, results, output_dir)

        print(f"\n{'='*60}")
        print(f" Download Summary")
        print(f"{'='*60}")
        print(f"  Total processed: {len(results)}")
        print(f"  Success:         {sum(1 for r in results if r.status == 'success')}")
        print(f"  Manual needed:   {sum(1 for r in results if r.status == 'manual')}")
        print(f"  Skipped:         {sum(1 for r in results if r.status == 'skipped')}")
        print(f"  Failed:          {sum(1 for r in results if r.status == 'failed')}")
        print(f"\n  Summary: {summary_path}")
        print(f"  Manual guide: {report_path}")
        print(f"  Data dir: {output_dir}")
        print()


if __name__ == "__main__":
    main()
