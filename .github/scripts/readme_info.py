#!/usr/bin/env python3
"""
GitHub Readme Info Generator（自建版）

替代已失效的 th3c0d3br34ker/github-readme-info：
  · 原版 Docker 镜像用 python-nodejs:latest，导致 matplotlib 3.3.0
    在 Python 3.12+ 无法编译
  · 原版硬编码 master 分支
  · 原版依赖已停运的 via.placeholder.com 和 github-contributions.now.sh

本脚本零编译依赖（仅用标准库），进度条用 Unicode 块字符。
只需要 GITHUB_TOKEN（Actions 自动注入），无需手动创建 PAT。
仅统计公开仓库数据。

环境变量：
  GITHUB_TOKEN  自动注入，或本地测试时用 GH_TOKEN
  GH_USERNAME   目标用户名；缺省时从 GITHUB_REPOSITORY 推断
  TIMEZONE      时区，默认 Asia/Shanghai
"""

import os
import re
import sys
import json
from collections import Counter
from datetime import datetime, timezone as dt_timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Shanghai")

# 从 "owner/repo" 推断用户名
_repo = os.environ.get("GITHUB_REPOSITORY", "")
USERNAME = os.environ.get("GH_USERNAME") or (_repo.split("/")[0] if "/" in _repo else "")

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
README_PATH = "README.md"
BAR_WIDTH = 22


# ──────────────────────────── HTTP ───────────────────────────────

def _headers():
    h = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-info-generator",
    }
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def rest(path):
    req = Request(API + path, headers=_headers())
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def graphql(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    req = Request(
        GRAPHQL,
        data=json.dumps(payload).encode("utf-8"),
        headers={**_headers(), "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(f"GraphQL: {data['errors']}")
    return data["data"]


# ────────────────────────── 格式化 ──────────────────────────────

def bar(percent, width=BAR_WIDTH):
    filled = max(0, min(width, int(round(percent / 100 * width))))
    return "█" * filled + "░" * (width - filled)


def fmt_int(n):
    return f"{n:,}"


def fmt_compact(n):
    for divisor, suffix in ((1_000_000_000, "billion"),
                            (1_000_000, "million"),
                            (1_000, "thousand")):
        if n >= divisor:
            v = n / divisor
            text = f"{v:.1f}".rstrip("0").rstrip(".")
            return f"{text} {suffix}"
    return str(n)


def to_local(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt_timezone.utc)
    if ZoneInfo:
        try:
            return dt.astimezone(ZoneInfo(TIMEZONE))
        except Exception:
            pass
    return dt


# ────────────────────────── 数据采集 ────────────────────────────

def _repos_via_rest(user):
    """REST 降级：列出公开非 fork 仓库（最多 100 个）"""
    repos = rest(f"/users/{user}/repos?per_page=100&type=owner&sort=pushed")
    return [r for r in repos if not r.get("fork")]


def fetch_commits(user):
    """公开仓库默认分支上本人的提交时间（最多 100 仓库 × 100 条）"""
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                     orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            name
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100) {
                    nodes { committedDate author { user { login } } }
                  }
                }
              }
            }
          }
        }
      }
    }
    """
    try:
        data = graphql(query, {"login": user})
        dates = []
        for repo in data["user"]["repositories"]["nodes"]:
            ref = repo.get("defaultBranchRef")
            if not ref:
                continue
            history = ((ref.get("target") or {}).get("history") or {}).get("nodes") or []
            for node in history:
                owner = ((node.get("author") or {}).get("user") or {}).get("login")
                if owner and owner.lower() != user.lower():
                    continue
                if node.get("committedDate"):
                    dates.append(node["committedDate"])
        return dates
    except Exception as exc:
        print(f"  ! GraphQL 失败（{exc}），改用 REST 采集", file=sys.stderr)

    # REST 降级路径
    dates = []
    try:
        repos = _repos_via_rest(user)
    except Exception as exc:
        print(f"  ! REST 也失败: {exc}", file=sys.stderr)
        return dates

    for repo in repos[:30]:
        owner, name = repo["owner"]["login"], repo["name"]
        try:
            commits = rest(f"/repos/{owner}/{name}/commits?per_page=100&author={user}")
        except Exception:
            continue
        for c in commits:
            date = ((c.get("commit") or {}).get("author") or {}).get("date")
            if date:
                dates.append(date)
    return dates


def fetch_languages(user):
    query = """
    query($login: String!) {
      user(login: $login) {
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          nodes { primaryLanguage { name } }
        }
      }
    }
    """
    counter = Counter()
    try:
        data = graphql(query, {"login": user})
        for repo in data["user"]["repositories"]["nodes"]:
            lang = repo.get("primaryLanguage")
            if lang and lang.get("name"):
                counter[lang["name"]] += 1
        return counter
    except Exception as exc:
        print(f"  ! GraphQL 失败（{exc}），改用 REST 采集语言", file=sys.stderr)

    try:
        for repo in _repos_via_rest(user):
            lang = repo.get("language")
            if lang:
                counter[lang] += 1
    except Exception as exc:
        print(f"  ! REST 也失败: {exc}", file=sys.stderr)
    return counter


def fetch_total_contributions(user):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar { totalContributions }
        }
      }
    }
    """
    try:
        data = graphql(query, {"login": user})
        cal = data["user"]["contributionsCollection"]["contributionCalendar"]
        return cal["totalContributions"], datetime.now().year
    except Exception as exc:
        print(f"  ! 取年度贡献失败: {exc}", file=sys.stderr)
        return 0, datetime.now().year


def fetch_lines_of_code(user):
    """统计公开非 fork 仓库的代码规模（当前快照行数）。

    不累加 code_frequency 的 additions-deletions：
    该端点会把仓库首次导入时的整个代码库记为「一周新增」，
    导致结果虚高几个数量级（实测 850 万行）。
    改为取每个仓库当前的语言字节数换算行数，更贴近真实规模。
    """
    total = 0
    try:
        repos = rest(f"/users/{user}/repos?per_page=100&type=owner")
    except HTTPError as exc:
        print(f"  ! 列出仓库失败: {exc}", file=sys.stderr)
        return 0

    for repo in repos:
        if repo.get("fork"):
            continue
        owner, name = repo["owner"]["login"], repo["name"]
        try:
            langs = rest(f"/repos/{owner}/{name}/languages")
        except HTTPError as exc:
            if exc.code not in (403, 404):
                print(f"  ! {name}: {exc}", file=sys.stderr)
            continue
        except Exception:
            continue
        # 代码平均每行约 40 字节（含缩进与空行）
        total += int(sum(langs.values()) / 40)
    return total


# ────────────────────────── 生成区块 ────────────────────────────

def block_loc(total):
    return f"**From Hello World I have written {fmt_compact(total)} Lines of Code ✍️**\n"


def block_contrib(total, year):
    return f"**🏆 {fmt_int(total)} Contributions in year {year}**\n"


def block_daily(dates):
    buckets = {"🌞 Morning": 0, "🌆 Daytime": 0, "🌃 Evening": 0, "🌙 Night": 0}
    for d in dates:
        h = to_local(d).hour
        if 6 <= h < 12:
            buckets["🌞 Morning"] += 1
        elif 12 <= h < 18:
            buckets["🌆 Daytime"] += 1
        elif 18 <= h < 24:
            buckets["🌃 Evening"] += 1
        else:
            buckets["🌙 Night"] += 1

    total = sum(buckets.values())
    if total == 0:
        return "**暂无提交记录**\n"

    early = buckets["🌞 Morning"] + buckets["🌆 Daytime"]
    late = buckets["🌃 Evening"] + buckets["🌙 Night"]
    title = "I'm an early 🐤" if early >= late else "I'm a night 🦉"

    rows = ["| 时段 | 提交 | 占比 |", "| :--- | ---: | :--- |"]
    for name, count in buckets.items():
        pct = round(count / total * 100, 1)
        rows.append(f"| {name} | {count} | `{bar(pct)}` {pct}% |")
    return f"**{title}**\n\n" + "\n".join(rows) + "\n"


def block_weekly(dates):
    names = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]
    counter = Counter(to_local(d).strftime("%A") for d in dates)
    total = sum(counter.values())
    if total == 0:
        return "**暂无提交记录**\n"

    best = max(names, key=lambda n: counter[n])
    rows = ["| 星期 | 提交 | 占比 |", "| :--- | ---: | :--- |"]
    for name in names:
        count = counter[name]
        pct = round(count / total * 100, 1)
        rows.append(f"| {name} | {count} | `{bar(pct)}` {pct}% |")
    return f"📅 **I'm Most Productive on {best}s**\n\n" + "\n".join(rows) + "\n"


def block_languages(counter):
    total = sum(counter.values())
    if total == 0:
        return "**暂无语言数据**\n"

    rows = ["| 语言 | 仓库 | 占比 |", "| :--- | ---: | :--- |"]
    for name, count in counter.most_common():
        pct = round(count / total * 100, 1)
        rows.append(f"| {name} | {count} | `{bar(pct)}` {pct}% |")
    top = counter.most_common(1)[0][0]
    return f"**My 💖 languages {top}**\n\n" + "\n".join(rows) + "\n"


# ────────────────────────── 写入 README ─────────────────────────

def replace_section(content, marker, body):
    """替换 <!--START_xxx:readme-info--> 与 <!--END_xxx:readme-info--> 之间的内容。

    marker 是完整名字，例如 SECTION_DAILY_COMMIT 或 CONTRIBUTIONS。
    """
    pattern = re.compile(
        r"(<!--START_" + marker + r":readme-info-->)"
        r"(.*?)"
        r"(<!--END_" + marker + r":readme-info-->)",
        re.DOTALL,
    )
    if not pattern.search(content):
        print(f"  - 跳过 {marker}（无对应标记）")
        return content
    print(f"  ✓ 写入 {marker}")
    return pattern.sub(
        lambda m: f"{m.group(1)}\n{body.strip()}\n{m.group(3)}", content
    )


def main():
    if not USERNAME:
        print("ERROR: 无法确定用户名", file=sys.stderr)
        return 1

    print(f"用户名: {USERNAME}   时区: {TIMEZONE}   Token: {'已注入' if TOKEN else '无（仅公开数据）'}")

    print("\n采集数据...")
    dates = fetch_commits(USERNAME)
    print(f"  · 提交样本: {len(dates)} 条")
    langs = fetch_languages(USERNAME)
    print(f"  · 语言种类: {len(langs)}")
    contrib, year = fetch_total_contributions(USERNAME)
    print(f"  · 年度贡献: {contrib}")
    loc = fetch_lines_of_code(USERNAME)
    print(f"  · 代码净增行数: {loc}")

    bodies = {
        "SECTION_LINES_OF_CODE": block_loc(loc),
        "CONTRIBUTIONS": block_contrib(contrib, year),
        "SECTION_DAILY_COMMIT": block_daily(dates),
        "SECTION_WEEKLY_COMMIT": block_weekly(dates),
        "SECTION_LANGUAGE": block_languages(langs),
    }

    with open(README_PATH, "r", encoding="utf-8") as fh:
        content = fh.read()

    print("\n写入 README...")
    for marker, body in bodies.items():
        content = replace_section(content, marker, body)

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)

    print("\n完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
