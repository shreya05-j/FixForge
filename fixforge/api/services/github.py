import httpx
from core.config import settings

async def post_pr_review_comment(repo_name: str, issue_number: str, markdown_body: str):
    """
    Posts a structured Markdown review comment to a GitHub PR or Issue.
    """
    if not settings.GITHUB_TOKEN:
        print("No GITHUB_TOKEN configured, skipping PR comment posting.")
        return
        
    url = f"https://api.github.com/repos/{repo_name}/issues/{issue_number}/comments"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json={"body": markdown_body})
        response.raise_for_status()
        return response.json()
