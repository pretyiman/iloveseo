import hashlib
import json
import re
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from lxml import etree

from app.services.render_client import RenderError, render
from app.services.tools.ai_crawlers import _is_path_blocked, _parse_robots_groups
from app.services.tools.base import Finding, ToolResult, score_from_findings
from app.services.tools.sitemap import _find_sitemaps_from_robots, _probe_common_paths

MAX_IMAGES_CHECKED_PER_PAGE = 15
MINHASH_NUM_HASHES = 8
NEAR_DUP_SIMILARITY_THRESHOLD = 0.8
JS_DIFF_SAMPLE_SIZE = 5
JS_DIFF_WORD_GAP_RATIO = 1.3  # rendered content >=30% larger than static -> likely JS-dependent

CONTENT_TYPE_WORD_THRESHOLDS = {"homepage": 100, "blog_post": 300, "service_page": 200, "other": 150}

SOFT_404_PHRASES = [
    "page not found",
    "404 not found",
    "we can't find that page",
    "this page doesn't exist",
    "the page you requested could not be found",
]

OnProgress = Callable[[int, int], Awaitable[None]]


@dataclass
class PageRecord:
    url: str
    depth: int
    status_code: int | None
    redirected: bool
    title: str | None
    meta_description: str | None
    canonical: str | None
    word_count: int
    content_type: str
    thin_content: bool
    h1_count: int
    heading_issues: list[str]
    broken_images: list[str]
    internal_link_count: int
    external_link_count: int
    mixed_content: list[str]
    structured_data_types: list[str]
    indexability: str
    is_soft_404: bool
    content_hash: str | None
    minhash: tuple[int, ...] | None
    fetch_error: str | None = None
    internal_links: list[str] = field(default_factory=list)


def _classify_content_type(path: str) -> str:
    if path in ("", "/"):
        return "homepage"
    if re.search(r"/(blog|news|articles?|posts?)/", path):
        return "blog_post"
    if re.search(r"/(services?|products?|solutions?)/", path):
        return "service_page"
    return "other"


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()


def _minhash(text: str, num_hashes: int = MINHASH_NUM_HASHES) -> tuple[int, ...] | None:
    words = re.findall(r"\w+", text.lower())
    shingles = {" ".join(words[i : i + 5]) for i in range(max(0, len(words) - 4))}
    if not shingles:
        return None
    signature = []
    for seed in range(num_hashes):
        min_hash = min(int(hashlib.md5(f"{seed}:{s}".encode()).hexdigest(), 16) for s in shingles)
        signature.append(min_hash)
    return tuple(signature)


def _similarity(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def _heading_issues(soup: BeautifulSoup) -> tuple[int, list[str]]:
    headings = soup.find_all(re.compile(r"^h[1-6]$"))
    issues: list[str] = []
    h1_count = sum(1 for h in headings if h.name == "h1")
    if h1_count == 0:
        issues.append("missing_h1")
    elif h1_count > 1:
        issues.append("multiple_h1")

    if any(not h.get_text(strip=True) for h in headings):
        issues.append("empty_heading")

    seen_level = 0
    for h in headings:
        level = int(h.name[1])
        if seen_level and level > seen_level + 1:
            issues.append("skipped_heading_level")
            break
        seen_level = level

    return h1_count, issues


def _is_soft_404(status_code: int, text: str, word_count: int) -> bool:
    if status_code != 200:
        return False
    lowered = text.lower()
    if any(phrase in lowered for phrase in SOFT_404_PHRASES):
        return True
    return word_count < 10


async def _check_broken_images(client: httpx.AsyncClient, page_url: str, soup: BeautifulSoup) -> list[str]:
    srcs = {urljoin(page_url, img.get("src")) for img in soup.find_all("img") if img.get("src")}
    broken = []
    for src in list(srcs)[:MAX_IMAGES_CHECKED_PER_PAGE]:
        try:
            resp = await client.head(src, follow_redirects=True, timeout=8)
            if resp.status_code >= 400:
                resp = await client.get(src, follow_redirects=True, timeout=8)
            if resp.status_code >= 400:
                broken.append(src)
        except httpx.HTTPError:
            broken.append(src)
    return broken


def _find_mixed_content(page_url: str, soup: BeautifulSoup) -> list[str]:
    if urlparse(page_url).scheme != "https":
        return []
    mixed = []
    for tag, attr in (("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src")):
        for el in soup.find_all(tag):
            value = el.get(attr)
            if value and value.strip().lower().startswith("http://"):
                mixed.append(value)
    return mixed


def _structured_data_types(soup: BeautifulSoup) -> list[str]:
    types: list[str] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if isinstance(item, dict) and item.get("@type"):
                t = item["@type"]
                types.extend(t if isinstance(t, list) else [t])
    return types


async def _analyze_page(
    client: httpx.AsyncClient, url: str, depth: int, robots_groups: dict[str, list[tuple[str, str]]]
) -> PageRecord:
    try:
        resp = await client.get(url, headers={"User-Agent": "SEORepairKit/1.0 (+audit)"}, follow_redirects=True)
    except httpx.HTTPError as exc:
        return PageRecord(
            url=url, depth=depth, status_code=None, redirected=False, title=None, meta_description=None,
            canonical=None, word_count=0, content_type=_classify_content_type(urlparse(url).path),
            thin_content=False, h1_count=0, heading_issues=[], broken_images=[], internal_link_count=0,
            external_link_count=0, mixed_content=[], structured_data_types=[], indexability="error_page",
            is_soft_404=False, content_hash=None, minhash=None, fetch_error=str(exc),
        )

    redirected = str(resp.url) != url
    domain = urlparse(url).netloc

    if resp.status_code >= 400:
        return PageRecord(
            url=url, depth=depth, status_code=resp.status_code, redirected=redirected, title=None,
            meta_description=None, canonical=None, word_count=0, content_type=_classify_content_type(urlparse(url).path),
            thin_content=False, h1_count=0, heading_issues=[], broken_images=[], internal_link_count=0,
            external_link_count=0, mixed_content=[], structured_data_types=[], indexability="error_page",
            is_soft_404=False, content_hash=None, minhash=None,
        )

    soup = BeautifulSoup(resp.text, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = desc_tag.get("content") if desc_tag else None
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else None
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots_content = (robots_tag.get("content", "") if robots_tag else "").lower()
    x_robots_tag = resp.headers.get("x-robots-tag", "").lower()

    text = _visible_text(resp.text)
    word_count = len(text.split())
    content_type = _classify_content_type(urlparse(url).path)
    thin_content = word_count < CONTENT_TYPE_WORD_THRESHOLDS[content_type]

    h1_count, heading_issues = _heading_issues(soup)
    broken_images = await _check_broken_images(client, str(resp.url), soup)
    mixed_content = _find_mixed_content(str(resp.url), soup)
    structured_data_types = _structured_data_types(soup)

    internal_links, external_links = [], []
    for a in soup.find_all("a", href=True):
        absolute = urljoin(str(resp.url), a["href"]).split("#")[0]
        if not absolute.startswith(("http://", "https://")):
            continue
        if urlparse(absolute).netloc == domain:
            internal_links.append(absolute)
        else:
            external_links.append(absolute)

    is_soft_404 = _is_soft_404(resp.status_code, text, word_count)

    if redirected:
        indexability = "redirected"
    elif "noindex" in robots_content:
        indexability = "noindex_tag"
    elif "noindex" in x_robots_tag:
        indexability = "noindex_header"
    elif canonical and canonical.rstrip("/") != str(resp.url).rstrip("/"):
        indexability = "canonicalized"
    elif _is_path_blocked(robots_groups.get("*", []), urlparse(url).path or "/"):
        indexability = "blocked_by_robots"
    elif is_soft_404:
        indexability = "soft_404"
    else:
        indexability = "indexable"

    return PageRecord(
        url=str(resp.url), depth=depth, status_code=resp.status_code, redirected=redirected, title=title,
        meta_description=meta_description, canonical=canonical, word_count=word_count, content_type=content_type,
        thin_content=thin_content, h1_count=h1_count, heading_issues=heading_issues, broken_images=broken_images,
        internal_link_count=len(internal_links), external_link_count=len(external_links),
        mixed_content=mixed_content, structured_data_types=structured_data_types, indexability=indexability,
        is_soft_404=is_soft_404, content_hash=hashlib.sha256(text.encode()).hexdigest() if text else None,
        minhash=_minhash(text), internal_links=internal_links,
    )


async def _discover_sitemap_urls(client: httpx.AsyncClient, base: str) -> set[str]:
    declared = await _find_sitemaps_from_robots(client, base)
    candidates = declared or [(await _probe_common_paths(client, base))[0]]
    candidates = [c for c in candidates if c]
    if not candidates:
        return set()

    urls: set[str] = set()
    try:
        resp = await client.get(candidates[0])
        root = etree.fromstring(resp.content)
        localname = root.tag.rsplit("}", 1)[-1]
        if localname == "urlset":
            for url_el in root:
                loc = next((c for c in url_el if c.tag.endswith("loc")), None)
                if loc is not None and loc.text:
                    urls.add(loc.text.strip())
        elif localname == "sitemapindex":
            child_locs = [
                c2.text.strip()
                for c in root
                for c2 in c
                if c2.tag.endswith("loc") and c2.text
            ][:3]
            for child_url in child_locs:
                try:
                    child_resp = await client.get(child_url)
                    child_root = etree.fromstring(child_resp.content)
                    for url_el in child_root:
                        loc = next((c for c in url_el if c.tag.endswith("loc")), None)
                        if loc is not None and loc.text:
                            urls.add(loc.text.strip())
                except (httpx.HTTPError, etree.XMLSyntaxError):
                    continue
    except (httpx.HTTPError, etree.XMLSyntaxError):
        return set()
    return urls


async def crawl_site(domain: str, max_pages: int, on_progress: OnProgress | None = None) -> dict:
    base = domain if domain.startswith("http") else f"https://{domain}"
    homepage = base.rstrip("/") or base

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            robots_resp = await client.get(f"{base}/robots.txt")
            robots_groups = _parse_robots_groups(robots_resp.text) if robots_resp.status_code < 400 else {}
        except httpx.HTTPError:
            robots_groups = {}

        sitemap_urls = await _discover_sitemap_urls(client, base)

        queue: deque[tuple[str, int]] = deque([(homepage, 0)])
        visited: set[str] = set()
        pages: dict[str, PageRecord] = {}
        inbound_counts: dict[str, int] = {}

        while queue and len(pages) < max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)

            record = await _analyze_page(client, url, depth, robots_groups)
            pages[record.url] = record

            if on_progress:
                await on_progress(len(pages), max_pages)

            if record.status_code and 200 <= record.status_code < 300:
                for link in record.internal_links:
                    inbound_counts[link] = inbound_counts.get(link, 0) + 1
                    if link not in visited and len(pages) + len(queue) < max_pages:
                        queue.append((link, depth + 1))

        js_diff_pages: list[str] = []
        for record in list(pages.values())[:JS_DIFF_SAMPLE_SIZE]:
            if record.fetch_error or not record.status_code:
                continue
            try:
                rendered = await render(record.url, timeout_ms=15000)
            except RenderError:
                continue
            rendered_word_count = len(_visible_text(rendered.get("rendered_html", "")).split())
            if record.word_count > 0 and rendered_word_count / max(record.word_count, 1) >= JS_DIFF_WORD_GAP_RATIO:
                js_diff_pages.append(record.url)

    return {
        "pages": list(pages.values()),
        "sitemap_urls": sitemap_urls,
        "inbound_counts": inbound_counts,
        "js_diff_pages": js_diff_pages,
        "max_pages": max_pages,
    }


def build_tool_result(crawl_data: dict) -> ToolResult:
    pages: list[PageRecord] = crawl_data["pages"]
    findings: list[Finding] = []

    thin = [p for p in pages if p.thin_content and p.status_code == 200]
    if thin:
        findings.append(Finding("medium", "thin_content_pages", f"{len(thin)} pages are below the expected word count for their type"))

    broken_img_pages = [p for p in pages if p.broken_images]
    if broken_img_pages:
        total_broken = sum(len(p.broken_images) for p in broken_img_pages)
        findings.append(Finding("medium", "broken_images", f"{total_broken} broken images found across {len(broken_img_pages)} pages"))

    heading_issue_pages = [p for p in pages if p.heading_issues]
    if heading_issue_pages:
        findings.append(Finding("low", "heading_structure_issues", f"{len(heading_issue_pages)} pages have heading structure issues (missing/multiple H1, skipped levels, or empty headings)"))

    mixed_content_pages = [p for p in pages if p.mixed_content]
    if mixed_content_pages:
        findings.append(Finding("high", "mixed_content", f"{len(mixed_content_pages)} pages load HTTP assets on an HTTPS page"))

    soft_404_pages = [p for p in pages if p.is_soft_404]
    if soft_404_pages:
        findings.append(Finding("medium", "soft_404s", f"{len(soft_404_pages)} pages appear to be soft-404s (200 OK but 'not found' content)"))

    non_indexable = [p for p in pages if p.indexability != "indexable"]
    if non_indexable:
        reasons: dict[str, int] = {}
        for p in non_indexable:
            reasons[p.indexability] = reasons.get(p.indexability, 0) + 1
        reason_str = ", ".join(f"{v} {k}" for k, v in reasons.items())
        findings.append(Finding("info", "non_indexable_pages", f"{len(non_indexable)} pages aren't indexable ({reason_str})"))

    error_pages = [p for p in pages if p.status_code is None or p.status_code >= 400]
    if error_pages:
        findings.append(Finding("high", "crawl_errors", f"{len(error_pages)} pages returned an error or failed to fetch"))

    signed_pages = [p for p in pages if p.minhash and p.status_code == 200]
    duplicate_clusters: list[list[str]] = []
    exact: dict[str, list[str]] = {}
    for p in signed_pages:
        if p.content_hash:
            exact.setdefault(p.content_hash, []).append(p.url)
    exact_dup_groups = [urls for urls in exact.values() if len(urls) > 1]
    dup_hashes = {h for h, urls in exact.items() if len(urls) > 1}

    seen: set[str] = set()
    for i, a in enumerate(signed_pages):
        if a.url in seen or a.content_hash in dup_hashes:
            continue
        cluster = [a.url]
        for b in signed_pages[i + 1 :]:
            if b.url in seen:
                continue
            if _similarity(a.minhash, b.minhash) >= NEAR_DUP_SIMILARITY_THRESHOLD:
                cluster.append(b.url)
                seen.add(b.url)
        if len(cluster) > 1:
            duplicate_clusters.append(cluster)
            seen.update(cluster)

    total_dup_groups = len(exact_dup_groups) + len(duplicate_clusters)
    if total_dup_groups:
        findings.append(Finding("medium", "duplicate_content", f"{total_dup_groups} groups of duplicate/near-duplicate pages found"))

    crawled_urls = {p.url for p in pages}
    sitemap_urls = crawl_data["sitemap_urls"]
    if sitemap_urls:
        missing_from_sitemap = crawled_urls - sitemap_urls
        never_crawled = sitemap_urls - crawled_urls
        if missing_from_sitemap:
            findings.append(Finding("low", "pages_missing_from_sitemap", f"{len(missing_from_sitemap)} crawled pages aren't in the sitemap"))
        if never_crawled:
            findings.append(Finding("info", "sitemap_urls_not_crawled", f"{len(never_crawled)} sitemap URLs were never reached while crawling (may be beyond the {crawl_data['max_pages']}-page limit)"))

    if crawl_data["js_diff_pages"]:
        findings.append(Finding("medium", "js_dependent_content", f"{len(crawl_data['js_diff_pages'])} sampled pages show significantly more content when JS-rendered than in raw HTML"))

    raw = {
        "pages_crawled": len(pages),
        "max_pages": crawl_data["max_pages"],
        "pages": [
            {
                "url": p.url, "depth": p.depth, "status_code": p.status_code, "title": p.title,
                "word_count": p.word_count, "content_type": p.content_type, "thin_content": p.thin_content,
                "h1_count": p.h1_count, "heading_issues": p.heading_issues, "broken_images": p.broken_images,
                "internal_link_count": p.internal_link_count, "external_link_count": p.external_link_count,
                "inbound_internal_links": crawl_data["inbound_counts"].get(p.url, 0),
                "mixed_content": p.mixed_content, "structured_data_types": p.structured_data_types,
                "indexability": p.indexability, "is_soft_404": p.is_soft_404, "fetch_error": p.fetch_error,
            }
            for p in pages
        ],
        "duplicate_clusters": exact_dup_groups + duplicate_clusters,
        "sitemap_coverage": {
            "sitemap_url_count": len(sitemap_urls),
            "crawled_not_in_sitemap": len(crawled_urls - sitemap_urls) if sitemap_urls else None,
            "sitemap_not_crawled": len(sitemap_urls - crawled_urls) if sitemap_urls else None,
        },
        "js_diff_pages": crawl_data["js_diff_pages"],
    }

    return ToolResult(tool="page_crawl", status="ok", score=score_from_findings(findings), findings=findings, raw=raw)
