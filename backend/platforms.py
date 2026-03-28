from urllib.parse import urlparse

from models import Platform


DEFAULT_TARGET_URLS = [
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
1. Starting from the provided URL, navigate to the site's jobs, careers, internships, or search experience.
2. If the site has a search box or filters, use them to search for the role and location.
3. Prefer recent, currently-open listings. If a recency filter exists, use the newest/recent option.
4. Dismiss cookie banners, popups, sign-in walls, or modal interruptions when possible.
5. Stay on the provided site unless the site itself opens its hosted jobs board.
6. Extract up to 15 of the best-matching listings visible during this run.

For each listing, return:
- job_title: string
- company_name: string
- location: string
- posted_time: string
- job_url: string
- salary: string or null
- employment_type: string or null

If the provided page is not already the jobs page, navigate to the appropriate careers/jobs section first.
Return only a JSON array. If no matching listings are found, return [].
""".strip()


def build_search_targets(role: str, location: str, keywords: list[str], target_urls: list[str] | None = None) -> list[dict]:
    """Build TinyFish automation targets from generic starting URLs."""
    raw_urls = target_urls or DEFAULT_TARGET_URLS
    targets: list[dict] = []

    for index, raw_url in enumerate(raw_urls):
        normalized_url = _normalize_url(raw_url)
        if not normalized_url:
            continue

        platform = infer_platform(normalized_url)
        label = get_platform_display_name(platform, normalized_url)
        targets.append({
            "id": f"{platform.value}_{index}",
            "platform": platform,
            "label": label,
            "url": normalized_url,
            "browser_profile": "stealth" if platform in {Platform.LINKEDIN, Platform.INDEED} else "lite",
            "goal": build_navigation_goal(role, location, keywords, normalized_url, label),
        })

    return targets
