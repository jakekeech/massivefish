from urllib.parse import quote
from models import Platform


UNIVERSAL_JOB_GOAL = """
Extract all job listings visible on this page. For each job, extract:
- job_title: string (the position title)
- company_name: string (the hiring company)
- location: string (where the job is located)
- posted_time: string (e.g. "2 hours ago", "Just posted")
- job_url: string (the full URL to apply or view the job posting)
- salary: string or null (compensation if shown)
- employment_type: string or null (Internship, Full-time, Part-time, Contract)

Dismiss any cookie banners, popups, or signup prompts that appear.
Scroll down 1-2 times to load more results if the page uses infinite scroll.
Stop after extracting 15-20 listings or reaching the end of results.
Return the results as a JSON array.
"""


def build_search_urls(role: str, location: str) -> list[dict]:
    """Build search URLs for all 6 job platforms."""
    role_encoded = quote(role)
    loc_encoded = quote(location)
    role_plus = role.replace(" ", "+")
    loc_plus = location.replace(" ", "+")

    return [
        {
            "platform": Platform.LINKEDIN,
            "url": f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location={loc_encoded}&f_TPR=r3600&sortBy=DD",
        },
        {
            "platform": Platform.INDEED,
            "url": f"https://www.indeed.com/jobs?q={role_encoded}&l={loc_encoded}&fromage=1&sort=date",
        },
        {
            "platform": Platform.WELLFOUND,
            "url": f"https://wellfound.com/role/l/{role_encoded}/{loc_encoded}",
        },
        {
            "platform": Platform.YC_WAAS,
            "url": f"https://www.workatastartup.com/jobs?query={role_encoded}&location={loc_encoded}",
        },
        {
            "platform": Platform.GREENHOUSE,
            "url": f"https://www.google.com/search?q={role_plus}+{loc_plus}+site:boards.greenhouse.io&tbs=qdr:d",
        },
        {
            "platform": Platform.LEVER,
            "url": f"https://www.google.com/search?q={role_plus}+{loc_plus}+site:jobs.lever.co&tbs=qdr:d",
        },
    ]


def get_platform_display_name(platform: Platform) -> str:
    """Get human-readable name for platform."""
    names = {
        Platform.LINKEDIN: "LinkedIn",
        Platform.INDEED: "Indeed",
        Platform.WELLFOUND: "Wellfound",
        Platform.YC_WAAS: "YC Startups",
        Platform.GREENHOUSE: "Greenhouse",
        Platform.LEVER: "Lever",
    }
    return names.get(platform, platform.value)
