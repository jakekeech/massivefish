from urllib.parse import quote_plus, urlparse

from models import Platform


DEFAULT_TARGET_URLS = [
    "https://www.indeed.com",
    "https://wellfound.com/jobs",
    "https://www.workatastartup.com/jobs",
    "https://www.linkedin.com",
]


def _normalize_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        return ""
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return f"https://{cleaned}"


def infer_platform(url: str) -> Platform:
    hostname = urlparse(url).netloc.lower()
    if "linkedin.com" in hostname:
        return Platform.LINKEDIN
    if "indeed.com" in hostname:
        return Platform.INDEED
    if "wellfound.com" in hostname:
        return Platform.WELLFOUND
    if "workatastartup.com" in hostname:
        return Platform.YC_WAAS
    if "greenhouse.io" in hostname:
        return Platform.GREENHOUSE
    if "lever.co" in hostname:
        return Platform.LEVER
    return Platform.CUSTOM


def get_platform_display_name(platform: Platform, fallback_url: str | None = None) -> str:
    """Get human-readable name for platform."""
    names = {
        Platform.LINKEDIN: "LinkedIn",
        Platform.INDEED: "Indeed",
        Platform.CUSTOM: "Custom Site",
        Platform.WELLFOUND: "Wellfound",
        Platform.YC_WAAS: "YC Startups",
        Platform.GREENHOUSE: "Greenhouse",
        Platform.LEVER: "Lever",
    }
    if platform != Platform.CUSTOM:
        return names.get(platform, platform.value)

    if not fallback_url:
        return names[Platform.CUSTOM]

    hostname = urlparse(fallback_url).netloc or fallback_url
    return hostname.replace("www.", "")


def build_navigation_goal(role: str, location: str, keywords: list[str], target_url: str, label: str) -> str:
    keyword_text = ", ".join(keywords) if keywords else "none"
    return f"""
You are starting at {target_url} ({label}).

Goal:
Find current job or internship listings relevant to:
- role/title: {role}
- preferred location: {location}
- keywords: {keyword_text}

Instructions:
1. Starting from the provided URL, if the page is already a job listing, extract the details from it. If not, navigate to the site's jobs, careers, internships, or search experience.
2. If the site has a search box or filters, use them to search for the role and location.
3. Prefer recent, currently-open listings. If a recency filter exists, use the newest/recent option.
4. Dismiss cookie banners, popups, sign-in walls, or modal interruptions when possible.
5. Stay on the provided site unless the site itself opens its hosted jobs board.
6. Extract up to 3 of the best-matching listings visible during this run.
7. Follow the output contract exactly. Do not rename keys, wrap the array in an object, or return markdown.

If the provided page is not already the jobs page, navigate to the appropriate careers/jobs section first.

Output contract:
- Respond with ONLY a valid JSON array.
- Every item in the array must use EXACTLY these keys:
  - job_title: string
  - company_name: string
  - location: string
  - posted_time: string
  - job_url: string
  - salary: string or null
  - employment_type: string or null
- Use empty strings for unknown string fields.
- Use null for unknown salary or employment_type.
- job_url must be the full absolute URL to the job posting, not a relative path.
- Do not include any extra keys.

Valid example:
[
  {{
    "job_title": "Software Engineer Intern",
    "company_name": "Example Co",
    "location": "San Francisco, CA",
    "posted_time": "2 days ago",
    "job_url": "https://example.com/jobs/123",
    "salary": null,
    "employment_type": "Internship"
  }}
]

If no matching listings are found, return [].
""".strip()


def build_platform_start_url(
    platform: Platform,
    normalized_url: str,
    role: str,
    location: str,
    keywords: list[str],
) -> str:
    parsed = urlparse(normalized_url)
    hostname = parsed.netloc.lower()
    path = (parsed.path or "/").rstrip("/") or "/"
    role_query = " ".join(part for part in [role, *keywords] if part).strip()
    encoded_role = quote_plus(role_query or role)
    encoded_location = quote_plus(location)

    if platform == Platform.INDEED and path == "/":
        return f"{parsed.scheme}://{hostname}/jobs?q={encoded_role}&l={encoded_location}&sort=date"

    if platform == Platform.LINKEDIN and path == "/":
        return f"{parsed.scheme}://{hostname}/jobs/search/?keywords={encoded_role}&location={encoded_location}&sortBy=DD"

    if platform == Platform.WELLFOUND and path == "/":
        return f"{parsed.scheme}://{hostname}/jobs"

    if platform == Platform.YC_WAAS and path == "/":
        return f"{parsed.scheme}://{hostname}/jobs"

    return normalized_url


def build_proxy_config(platform: Platform, normalized_url: str) -> dict | None:
    hostname = urlparse(normalized_url).netloc.lower()

    if platform in {Platform.LINKEDIN, Platform.INDEED} and hostname.endswith(".com"):
        return {
            "enabled": True,
            "country_code": "US",
        }

    return None


def build_search_targets(role: str, location: str, keywords: list[str], target_urls: list[str] | None = None) -> list[dict]:
    """Build TinyFish automation targets from generic starting URLs."""
    raw_urls = target_urls or DEFAULT_TARGET_URLS
    targets: list[dict] = []

    for index, raw_url in enumerate(raw_urls):
        normalized_url = _normalize_url(raw_url)
        if not normalized_url:
            continue

        platform = infer_platform(normalized_url)
        start_url = build_platform_start_url(platform, normalized_url, role, location, keywords)
        label = get_platform_display_name(platform, normalized_url)
        proxy_config = build_proxy_config(platform, normalized_url)
        targets.append({
            "id": f"{platform.value}_{index}",
            "platform": platform,
            "label": label,
            "url": start_url,
            # Use the fuller browser profile for all sites so TinyFish can expose
            # a live browser stream consistently instead of falling back to a
            # lighter session that may not emit STREAMING_URL.
            "browser_profile": "stealth",
            "proxy_config": proxy_config,
            "goal": build_navigation_goal(role, location, keywords, start_url, label),
        })

    return targets
