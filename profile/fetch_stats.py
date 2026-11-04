"""Fetch public GitHub numbers for the profile and write stats.json.

Needs GITHUB_TOKEN for the contribution calendar (GraphQL). Any section that fails
keeps its previous value, so a bad API day never breaks the README.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")


def request(url, body=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "profile-stats"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as resp:
        return json.load(resp)


def rest(path, **params):
    return request(f"{API}{path}?{urllib.parse.urlencode(params)}")


def graphql(query, **variables):
    out = request(f"{API}/graphql", {"query": query, "variables": variables})
    if out.get("errors"):
        raise RuntimeError(out["errors"])
    return out["data"]


def public_repos(login):
    repos, page = [], 1
    while True:
        batch = rest(f"/users/{login}/repos", type="owner", per_page=100, page=page)
        repos += [r for r in batch if not r["private"]]
        if len(batch) < 100:
            return repos
        page += 1


def languages(repos):
    """Primary languages by repo count; ties go to the language pushed to most recently."""
    own = [r for r in repos if not r["fork"] and r["language"]]
    count = Counter(r["language"] for r in own)
    latest = {}
    for r in own:
        latest[r["language"]] = max(latest.get(r["language"], ""), r["pushed_at"] or "")
    out = [[name, n] for name, n in count.items()]
    out.sort(key=lambda x: latest[x[0]], reverse=True)
    out.sort(key=lambda x: -x[1])
    return out


def calendar(login, today):
    years = graphql("query($l:String!){user(login:$l){contributionsCollection{contributionYears}}}", l=login)
    days = {}
    for year in sorted(years["user"]["contributionsCollection"]["contributionYears"]):
        data = graphql(
            "query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){contributionsCollection(from:$f,to:$t)"
            "{contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}",
            l=login, f=f"{year}-01-01T00:00:00Z", t=f"{year}-12-31T23:59:59Z",
        )
        for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in week["contributionDays"]:
                if d["date"] <= today.isoformat():
                    days[d["date"]] = d["contributionCount"]
    return days


def streaks(days, today):
    """Current streak counts back from today, or from yesterday when today has no contributions yet."""
    active = {d for d, n in days.items() if n > 0}
    day = today if today.isoformat() in active else today - timedelta(days=1)
    current = 0
    while day.isoformat() in active:
        current += 1
        day -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(active):
        cur = date.fromisoformat(d)
        run = run + 1 if prev and cur - prev == timedelta(days=1) else 1
        best, prev = max(best, run), cur
    return current, best


def commits_by_year(login, first_year, today):
    out = []
    for year in range(first_year, today.year + 1):
        res = rest("/search/commits", q=f"author:{login} author-date:{year}-01-01..{year}-12-31", per_page=1)
        out.append([year, res["total_count"]])
    return out


def recent_commits(login, n=3):
    """Latest commit in each of the n most recently active public repos, skipping this profile repo."""
    seen, out = set(), []
    for page in range(1, 6):
        res = rest("/search/commits", q=f"author:{login}", sort="author-date", order="desc", per_page=100, page=page)
        for item in res["items"]:
            repo = item["repository"]
            if repo["private"] or repo["fork"] or repo["name"].lower() == login.lower() or repo["name"] in seen:
                continue
            seen.add(repo["name"])
            out.append({
                "date": item["commit"]["author"]["date"][:10],
                "repo": repo["name"],
                "sha": item["sha"][:7],
                "message": item["commit"]["message"].split("\n")[0],
            })
            if len(out) == n:
                return out
        if len(res["items"]) < 100:
            break
    return out


def section(stats, name, fn):
    try:
        stats.update(fn())
    except Exception as e:  # keep the previous values for this section
        print(f"warning: {name} not updated: {e}", file=sys.stderr)


def main():
    cfg = json.loads((HERE / "config.json").read_text())
    login = cfg["login"]
    path = HERE / "stats.json"
    stats = json.loads(path.read_text()) if path.exists() else {}
    today = date.today()
    stats["today"] = today.isoformat()

    def repo_stats():
        repos = public_repos(login)
        return {"repos": len(repos), "languages": languages(repos)}

    def contribution_stats():
        days = calendar(login, today)
        current, best = streaks(days, today)
        return {"since": min(d for d, n in days.items() if n > 0), "contributions": sum(days.values()),
                "streak": current, "best": best}

    section(stats, "repos", repo_stats)
    if TOKEN:
        section(stats, "contributions", contribution_stats)
    first_year = int(stats.get("since", f"{today.year}")[:4])
    section(stats, "commits by year", lambda: {"commits_by_year": commits_by_year(login, first_year, today)})
    section(stats, "recent commits", lambda: {"recent_commits": recent_commits(login)})
    path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
