"""Scrapes AI/ML job postings from top tech companies with Singapore offices."""

import re
import json
import time
import hashlib
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
}

AI_KEYWORDS = [
    r"\bAI\b", r"\bA\.I\b", r"Artificial Intelligence",
    r"Machine Learning", r"\bML\b", r"Deep Learning",
    r"Natural Language Processing", r"\bNLP\b",
    r"Computer Vision", r"\bLLM\b", r"Large Language Model",
    r"Generative AI", r"Gen\s?AI",
    r"Applied AI", r"AI/ML",
    r"Neural Network", r"Transformer",
    r"Reinforcement Learning", r"\bRLHF\b",
    r"Speech Recognition", r"Recommender System",
]
AI_PATTERN = re.compile("|".join(AI_KEYWORDS), re.IGNORECASE)
SG_PATTERN = re.compile(r"Singapore|SGP", re.IGNORECASE)


def job_id(title: str, company: str, url: str) -> str:
    raw = f"{company.lower()}::{title.lower()}::{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def is_ai_role(text: str) -> bool:
    return bool(AI_PATTERN.search(text))


def is_singapore(location: str) -> bool:
    return bool(SG_PATTERN.search(location))


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_job(title, company, location, url, posted_date="", source="unknown") -> dict:
    return {
        "id": job_id(title, company, url),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "posted_date": posted_date[:10] if posted_date else "",
        "first_seen": now_iso(),
        "last_seen": now_iso(),
        "active": True,
        "source": source,
    }


# ═══════════════════════════════════════════════════════════════════════
# Greenhouse (API)
# ═══════════════════════════════════════════════════════════════════════

# (display_name, board_slug) — only slugs verified to work
GREENHOUSE_COMPANIES = [
    ("Stripe", "stripe"),
    ("MongoDB", "mongodb"),
    ("Anthropic", "anthropic"),
    ("Cloudflare", "cloudflare"),
    ("GitLab", "gitlab"),
    ("Figma", "figma"),
    ("Duolingo", "duolingo"),
    ("Reddit", "reddit"),
    ("Twilio", "twilio"),
    ("Brex", "brex"),
    ("Chime", "chime"),
    ("Flexport", "flexport"),
    ("HubSpot", "hubspot"),
    ("Postman", "postman"),
    ("Samsara", "samsara"),
    ("Squarespace", "squarespace"),
    ("Toast", "toast"),
    ("Vercel", "vercel"),
    ("Webflow", "webflow"),
    ("Zscaler", "zscaler"),
    ("Databricks", "databricks"),
    ("Airbnb", "airbnb"),
    ("Dropbox", "dropbox"),
    ("Instacart", "instacart"),
    # Verified manually (may need updating over time):
    ("Discord", "discord"),
    ("Robinhood", "robinhood"),
    ("Roblox", "roblox"),
]

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"


def scrape_greenhouse(name: str, board: str) -> list[dict]:
    url = GREENHOUSE_API.format(board=board)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  [!] {e}")
        return []

    results = []
    for job in data.get("jobs", []):
        title = job.get("title", "")
        location = job.get("location", {}).get("name", "")
        if not is_singapore(location):
            continue
        if not is_ai_role(title):
            continue
        results.append(new_job(
            title=title,
            company=name,
            location=location,
            url=job.get("absolute_url", ""),
            posted_date=job.get("updated_at", ""),
            source="greenhouse",
        ))
    return results


# ═══════════════════════════════════════════════════════════════════════
# Google (HTML scrape)
# ═══════════════════════════════════════════════════════════════════════

GOOGLE_URL = (
    "https://www.google.com/about/careers/applications/jobs/results/"
    "?location=Singapore&q=AI+Engineer+Machine+Learning"
)


def scrape_google() -> list[dict]:
    results = []
    try:
        resp = requests.get(GOOGLE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for card in soup.select("li, div[role], article, [data-id]"):
            link = card.select_one("a[href]")
            if not link:
                continue
            href = link.get("href", "")
            # Skip navigation / non-job links
            if "jobs/results" not in href and "/job" not in href:
                continue
            title_el = card.select_one("h2, h3, [class*='title']")
            title = title_el.get_text(strip=True) if title_el else card.get_text(" ", strip=True)[:80]
            # Skip boilerplate nav and non-job text
            if any(skip in title.lower() for skip in ("recommended jobs", "saved jobs", "job alerts", "search results")):
                continue
            if not is_ai_role(title):
                link_text = link.get_text(" ", strip=True) if link else ""
                if not is_ai_role(link_text):
                    continue
            # Build full URL
            if href.startswith("http"):
                url = href
            elif href.startswith("./"):
                url = f"https://www.google.com/about/careers/applications{href[1:]}"
            elif href.startswith("/"):
                url = f"https://www.google.com/about/careers/applications{href}"
            else:
                url = f"https://www.google.com/about/careers/applications/{href}"
            results.append(new_job(
                title=title,
                company="Google",
                location="Singapore",
                url=url,
                source="google",
            ))
    except Exception as e:
        print(f"  [!] {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Amazon (JSON API)
# ═══════════════════════════════════════════════════════════════════════

AMAZON_URL = (
    "https://www.amazon.jobs/en/search.json"
    "?location=Singapore"
    "&category%5B%5D=machine-learning-science"
    "&category%5B%5D=software-development"
    "&category%5B%5D=data-science"
    "&offset=0&result_limit=100&sort=recent"
)


def scrape_amazon() -> list[dict]:
    results = []
    try:
        resp = requests.get(AMAZON_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            location = job.get("city_country", "") or job.get("location", "")
            if not is_singapore(location):
                continue
            if not is_ai_role(title):
                desc = job.get("description", "")
                if not is_ai_role(desc):
                    continue
            jid = job.get("id_icims", "")
            results.append(new_job(
                title=title,
                company="Amazon",
                location=location,
                url=f"https://www.amazon.jobs/en/jobs/{jid}" if jid else "",
                posted_date=job.get("posted_date", ""),
                source="amazon",
            ))
    except Exception as e:
        print(f"  [!] {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Apple (embedded JSON in HTML)
# ═══════════════════════════════════════════════════════════════════════

APPLE_URL = "https://jobs.apple.com/en-sg/search?location=singapore-SGP"


def scrape_apple() -> list[dict]:
    results = []
    try:
        resp = requests.get(APPLE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for script in soup.find_all("script"):
            text = script.string or ""
            # Apple embeds job data as escaped JSON in a <script> tag
            # Look for the searchResults array inside the "search" key
            sr_idx = text.find('searchResults')
            pipe_idx = text.find('PIPE-')
            if sr_idx < 0 or pipe_idx < 0:
                continue
            # Find the [ that starts the array
            bracket_start = text.find('[', sr_idx)
            if bracket_start < 0:
                continue
            # Count brackets to find matching ]
            depth = 0
            bracket_end = bracket_start
            for i in range(bracket_start, len(text)):
                if text[i] == '[':
                    depth += 1
                elif text[i] == ']':
                    depth -= 1
                    if depth == 0:
                        bracket_end = i + 1
                        break
            # Extract and unescape \"
            raw = text[bracket_start:bracket_end]
            decoded = raw.replace('\\"', '"').replace('\\\\', '\\')
            try:
                postings = json.loads(decoded)
            except json.JSONDecodeError:
                continue
            for posting in postings:
                title = posting.get("postingTitle", "")
                if not is_ai_role(title):
                    continue
                locations = posting.get("locations", [])
                loc_names = [l.get("name", "") for l in locations]
                loc_str = ", ".join(loc_names)
                if not is_singapore(loc_str):
                    continue
                pid = posting.get("positionId", "")
                results.append(new_job(
                    title=title,
                    company="Apple",
                    location=loc_str,
                    url=f"https://jobs.apple.com/en-sg/details/{pid}" if pid else "",
                    posted_date=posting.get("postingDate", ""),
                    source="apple",
                ))
            break
    except Exception as e:
        print(f"  [!] {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# ByteDance / TikTok (HTML scrape from joinbytedance.com)
# ═══════════════════════════════════════════════════════════════════════

BYTEDANCE_URL = (
    "https://job-boards.greenhouse.io/tiktok"
)

BYTEDANCE_FALLBACK = (
    "https://joinbytedance.com/search"
    "?keyword=AI+Engineer&location_code_list=Singapore"
)


def scrape_bytedance() -> list[dict]:
    """Try TikTok Greenhouse board; fall back to joinbytedance HTML."""
    results = []

    # Primary: TikTok Greenhouse board
    try:
        url = "https://boards-api.greenhouse.io/v1/boards/tiktok/jobs?content=true"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        for job in data.get("jobs", []):
            title = job.get("title", "")
            location = job.get("location", {}).get("name", "")
            if not is_singapore(location):
                continue
            if not is_ai_role(title):
                continue
            results.append(new_job(
                title=title,
                company="ByteDance",
                location=location,
                url=job.get("absolute_url", ""),
                posted_date=job.get("updated_at", ""),
                source="bytedance",
            ))
    except Exception:
        pass  # fall through to fallback

    # Fallback: joinbytedance.com
    if not results:
        try:
            resp = requests.get(BYTEDANCE_FALLBACK, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            for script in soup.find_all("script"):
                text = script.string or ""
                if "jobList" not in text and "positionList" not in text:
                    continue
                m = re.search(r'(?:jobList|positionList)["\']?\s*[:=]\s*(\[.*?\])', text, re.DOTALL)
                if not m:
                    continue
                try:
                    jobs = json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
                for job in jobs:
                    title = job.get("title", "")
                    city = job.get("city", "") or job.get("location", "")
                    if not is_singapore(city):
                        continue
                    if not is_ai_role(title):
                        continue
                    jid = job.get("id", "")
                    results.append(new_job(
                        title=title,
                        company="ByteDance",
                        location=city,
                        url=f"https://jobs.bytedance.com/en/position/{jid}/detail" if jid else "",
                        posted_date=job.get("createTime", ""),
                        source="bytedance",
                    ))
                break
        except Exception as e:
            print(f"  [!] ByteDance fallback: {e}")

    return results


# ═══════════════════════════════════════════════════════════════════════
# Meta (client-rendered; minimal best-effort)
# ═══════════════════════════════════════════════════════════════════════

def scrape_meta() -> list[dict]:
    """Meta's career page is fully client-rendered — best effort only."""
    try:
        resp = requests.get(
            "https://www.metacareers.com/jobsearch/?q=AI+Engineer&locations=Singapore",
            headers=HEADERS, timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Check for __NEXT_DATA__ or embedded state
        for script in soup.find_all("script"):
            text = script.string or ""
            if "jobPostings" in text or '"jobs"' in text:
                print("  [i] Meta: embedded data found but parsing not yet implemented")
                break
        else:
            print("  [i] Meta: fully client-rendered, no data extracted")
    except Exception as e:
        print(f"  [!] Meta: {e}")
    return []


# ═══════════════════════════════════════════════════════════════════════
# Microsoft (client-rendered; minimal best-effort)
# ═══════════════════════════════════════════════════════════════════════

def scrape_microsoft() -> list[dict]:
    """Microsoft redirects to a client-rendered app — best effort."""
    try:
        resp = requests.get(
            "https://jobs.careers.microsoft.com/global/en/search?lc=Singapore&q=AI%20Engineer",
            headers=HEADERS, timeout=30,
        )
        resp.raise_for_status()
        print("  [i] Microsoft: client-rendered app, no data extracted")
    except Exception as e:
        print(f"  [!] Microsoft: {e}")
    return []


# ═══════════════════════════════════════════════════════════════════════
# Shopee (HTML scrape)
# ═══════════════════════════════════════════════════════════════════════

SHOPEE_URL = "https://careers.shopee.sg/search?keyword=AI%20Engineer"


def scrape_shopee() -> list[dict]:
    results = []
    try:
        resp = requests.get(SHOPEE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Shopee career page is mostly client-rendered; try to find API data
        for script in soup.find_all("script"):
            text = script.string or ""
            if "jobList" not in text and "jobs" not in text.lower():
                continue
            # Try to find embedded JSON
            for match in re.finditer(r'\[.*?"title".*?\]', text, re.DOTALL):
                try:
                    data = json.loads(match.group(0))
                    if not isinstance(data, list):
                        continue
                    for job in data:
                        if not isinstance(job, dict):
                            continue
                        title = job.get("title", "") or job.get("jobName", "")
                        if not is_ai_role(title):
                            continue
                        jid = job.get("id", "") or job.get("jobId", "")
                        results.append(new_job(
                            title=title,
                            company="Shopee",
                            location="Singapore",
                            url=f"https://careers.shopee.sg/job-detail/{jid}" if jid else "",
                            source="shopee",
                        ))
                    break
                except json.JSONDecodeError:
                    continue
            if results:
                break
        if not results:
            print("  [i] Shopee: no embedded data found (likely client-rendered)")
    except Exception as e:
        print(f"  [!] Shopee: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Snowflake (Greenhouse)
# ═══════════════════════════════════════════════════════════════════════

def scrape_snowflake() -> list[dict]:
    """Snowflake uses greenhouse with a custom subdomain."""
    try:
        url = "https://careers.snowflake.com/api/jobs?location=Singapore&limit=100"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for job in data.get("jobs", data if isinstance(data, list) else []):
            if isinstance(job, dict):
                title = job.get("title", "")
                location = job.get("location", "") or job.get("categories", "")
                if not is_singapore(location):
                    continue
                if not is_ai_role(title):
                    continue
                jid = job.get("id", "")
                results.append(new_job(
                    title=title,
                    company="Snowflake",
                    location=location,
                    url=job.get("url", f"https://careers.snowflake.com/jobs/{jid}") if jid else "",
                    source="snowflake",
                ))
        return results
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════
# LinkedIn (aggregator)
# ═══════════════════════════════════════════════════════════════════════

LINKEDIN_URL = (
    "https://www.linkedin.com/jobs/search/"
    "?keywords=AI%20Engineer%20Machine%20Learning"
    "&location=Singapore"
)


def clean_linkedin_location(raw: str) -> str:
    """Remove trailing metadata like 'Be an early applicant2 weeks ago'."""
    # Trim suffixes like "X days ago", "X weeks ago", "Be an early applicant", etc.
    raw = re.sub(
        r"(\d+\s+(day|week|month|hour|minute|year)s?\s+ago|"
        r"Be an early applicant|"
        r"Actively recruiting|"
        r"via LinkedIn|"
        r"Reposted).*$",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip(" ,")
    return raw


def scrape_linkedin() -> list[dict]:
    results = []
    try:
        resp = requests.get(LINKEDIN_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select(".base-card, .job-search-card, [data-job-id]")
        for card in cards:
            title_el = card.select_one(
                ".base-search-card__title, .job-search-card__title, h3"
            )
            company_el = card.select_one(
                ".base-search-card__subtitle, .job-search-card__subtitle, h4"
            )
            loc_el = card.select_one(
                ".job-search-card__location, .base-search-card__metadata"
            )
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view']")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True) if company_el else "Unknown"
            location = clean_linkedin_location(
                loc_el.get_text(strip=True) if loc_el else ""
            )
            url = link_el.get("href", "")
            if not is_ai_role(title):
                continue
            results.append(new_job(
                title=title,
                company=company,
                location=location,
                url=url,
                source="linkedin",
            ))
    except Exception as e:
        print(f"  [!] {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# MyCareersFuture (Singapore government portal)
# ═══════════════════════════════════════════════════════════════════════

MCF_URL = "https://api.mycareersfuture.gov.sg/v2/jobs?search=AI%20Engineer%20Machine%20Learning&limit=100"


def scrape_mcf() -> list[dict]:
    results = []
    try:
        resp = requests.get(MCF_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        jobs = data.get("results", data.get("jobs", []))
        for job in jobs:
            title = job.get("title", "")
            company = (
                job.get("company", {}).get("name", "Unknown")
                if isinstance(job.get("company"), dict)
                else job.get("company", "Unknown")
            )
            if not is_ai_role(title):
                desc = job.get("description", "")
                if not is_ai_role(desc):
                    continue
            jid = job.get("uuid", "") or job.get("id", "")
            results.append(new_job(
                title=title,
                company=company,
                location="Singapore",
                url=f"https://www.mycareersfuture.gov.sg/job/{jid}" if jid else "",
                posted_date=job.get("postedDate", ""),
                source="mcf",
            ))
    except Exception as e:
        print(f"  [!] {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Orchestration
# ═══════════════════════════════════════════════════════════════════════

# Each entry is (label, callable)
SCRAPERS = []

# Greenhouse companies
for display_name, board_slug in GREENHOUSE_COMPANIES:
    # factory so each closure captures its own name/board
    def _make_gh(n, b):
        def _fn():
            return scrape_greenhouse(n, b)
        return _fn
    SCRAPERS.append((f"Greenhouse/{display_name}", _make_gh(display_name, board_slug)))

# Direct company scrapers
SCRAPERS += [
    ("Google", scrape_google),
    ("Amazon", scrape_amazon),
    ("Apple", scrape_apple),
    ("ByteDance", scrape_bytedance),
    ("Meta", scrape_meta),
    ("Microsoft", scrape_microsoft),
    ("Shopee", scrape_shopee),
    ("Snowflake", scrape_snowflake),
    ("LinkedIn", scrape_linkedin),
    ("MyCareersFuture", scrape_mcf),
]


def run_all() -> list[dict]:
    all_jobs: list[dict] = []
    for label, scraper_fn in SCRAPERS:
        print(f"[*] {label}...", end=" ", flush=True)
        start = time.time()
        try:
            jobs = scraper_fn()
        except Exception as e:
            print(f"crashed: {e}")
            jobs = []
        elapsed = time.time() - start
        print(f"{len(jobs)} roles ({elapsed:.1f}s)")
        all_jobs.extend(jobs)

    # Deduplicate by id
    seen: set[str] = set()
    deduped: list[dict] = []
    for job in all_jobs:
        jid = job["id"]
        if jid not in seen:
            seen.add(jid)
            deduped.append(job)

    print(f"\n[=] Total unique AI roles in Singapore: {len(deduped)}")
    return deduped


if __name__ == "__main__":
    jobs = run_all()
    print(json.dumps(jobs, indent=2, ensure_ascii=False))
