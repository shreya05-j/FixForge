"""
github.py — GitHub API integration for FixForge.

Default: GITHUB_DRY_RUN=true.
  - Dry run: logs the exact comment that WOULD be posted. No network call made.
  - Live run: posts to /repos/{owner}/{repo}/issues/{number}/comments.

To enable live posting set GITHUB_DRY_RUN=false in .env AND provide GITHUB_TOKEN.
"""

import sys
import logging
import httpx
from core.config import settings

logger = logging.getLogger(__name__)

DRY_RUN_SEPARATOR = "=" * 72


async def post_pr_review_comment(repo_name: str, issue_number: str, markdown_body: str) -> dict:
    """
    Posts a structured Markdown review comment to a GitHub issue/PR.

    Dry-run mode (GITHUB_DRY_RUN=true, default):
        Logs the exact comment that would be posted. Never makes a network call.
        Returns {"dry_run": True, "would_post_to": url, "body_length": n}.

    Live mode (GITHUB_DRY_RUN=false):
        Requires GITHUB_TOKEN. Posts to GitHub REST API.
        Returns the GitHub API response JSON.
    """
    url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/comments"

    if settings.GITHUB_DRY_RUN:
        logger.info(
            "[GITHUB DRY-RUN] Would POST to: %s\n%s\n%s\n%s",
            url, DRY_RUN_SEPARATOR, markdown_body, DRY_RUN_SEPARATOR,
        )
        try:
            print(markdown_body)
        except UnicodeEncodeError:
            print(markdown_body.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
        print(DRY_RUN_SEPARATOR)
        return {"dry_run": True, "would_post_to": url, "body_length": len(markdown_body)}

    # --- Live path ---
    if not settings.GITHUB_TOKEN:
        logger.warning(
            "GITHUB_DRY_RUN=false but GITHUB_TOKEN is empty. Skipping comment posting. "
            "Set GITHUB_TOKEN in .env to enable live posting."
        )
        return {"dry_run": False, "skipped": True, "reason": "GITHUB_TOKEN not set"}

    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json={"body": markdown_body})
        response.raise_for_status()
        result = response.json()
        logger.info("GitHub comment posted: %s", result.get("html_url", "unknown"))
        return result
