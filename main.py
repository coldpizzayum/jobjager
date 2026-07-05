"""Job alert bot: poll ATS APIs, filter, and push new jobs to Telegram.

Usage:
    python main.py            # normal run (needs TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)
    python main.py --check    # verify each company's API works, print counts, no Telegram
    DRY_RUN=1 python main.py  # full run but print messages instead of sending
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "companies.json"
SEEN_PATH = ROOT / "seen.json"
TIMEOUT = 30
HEADERS = {"User-Agent": "job-alert-bot/1.0 (personal job search)"}


# ---------------------------------------------------------------- fetchers

def fetch_greenhouse(company):
    region = company.get("region", "us")
    base = (
        "https://boards-api.eu.greenhouse.io"
        if region == "eu"
        else "https://boards-api.greenhouse.io"
    )
    url = f"{base}/v1/boards/{company['token']}/jobs"
    r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append({
            "id": f"greenhouse-{company['token']}-{j['id']}",
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
        })
    return jobs


def fetch_ashby(company):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{company['token']}"
    r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        locations = [j.get("location") or ""]
        locations += [s.get("location", "") for s in j.get("secondaryLocations", [])]
        jobs.append({
            "id": f"ashby-{company['token']}-{j['id']}",
            "title": j.get("title", ""),
            "location": " / ".join(x for x in locations if x),
            "url": j.get("jobUrl") or j.get("applyUrl", ""),
        })
    return jobs


def fetch_workable(company):
    url = f"https://apply.workable.com/api/v1/widget/accounts/{company['token']}"
    r = requests.get(url, timeout=TIMEOUT, headers=HEADERS)
    r.raise_for_status()
    jobs = []
    for j in r.json().get("jobs", []):
        loc = ", ".join(x for x in [j.get("city", ""), j.get("country", "")] if x)
        jobs.append({
            "id": f"workable-{company['token']}-{j.get('shortcode') or j.get('code')}",
            "title": j.get("title", ""),
            "location": loc,
            "url": j.get("url", ""),
        })
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
}


# ---------------------------------------------------------------- filtering

def compile_patterns(words):
    return [re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in words]


def title_matches(title, include, exclude):
    if include and not any(p.search(title) for p in include):
        return False
    if any(p.search(title) for p in exclude):
        return False
    return True


def location_matches(location, allowed):
    if not allowed:
        return True
    if not location:
        return True  # keep jobs with no stated location, better safe than missed
    loc = location.lower()
    return any(a in loc for a in allowed)


# ---------------------------------------------------------------- telegram

def send_telegram(text):
    if os.environ.get("DRY_RUN"):
        print("---- DRY RUN, would send: ----")
        print(text)
        return
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_messages(new_by_company, first_run):
    header = (
        "📋 初始快照:目前所有符合條件的職缺"
        if first_run
        else "🔔 發現新職缺!"
    )
    lines = [header, ""]
    for name, jobs in new_by_company.items():
        lines.append(f"<b>{esc(name)}</b>")
        for j in jobs:
            loc = f" — {esc(j['location'])}" if j["location"] else ""
            lines.append(f"• <a href=\"{j['url']}\">{esc(j['title'])}</a>{loc}")
        lines.append("")
    # split into chunks under Telegram's 4096-char limit
    messages, current = [], ""
    for line in lines:
        if len(current) + len(line) + 1 > 3800:
            messages.append(current.rstrip())
            current = ""
        current += line + "\n"
    if current.strip():
        messages.append(current.rstrip())
    return messages


# ---------------------------------------------------------------- main

def main():
    check_mode = "--check" in sys.argv

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    filters = config.get("filters", {})
    include = compile_patterns(filters.get("title_keywords", []))
    exclude = compile_patterns(filters.get("title_exclude", []))
    allowed_locations = [x.lower() for x in filters.get("locations", [])]

    first_run = not SEEN_PATH.exists()
    seen = {} if first_run else json.loads(SEEN_PATH.read_text(encoding="utf-8"))

    new_by_company = {}
    warnings = []

    for company in config["companies"]:
        name, ats = company["name"], company["ats"]
        try:
            jobs = FETCHERS[ats](company)
        except Exception as e:
            warnings.append(f"{name}: 抓取失敗 ({type(e).__name__}: {e})")
            continue  # keep old seen state for this company

        if check_mode:
            matches = [
                j for j in jobs
                if title_matches(j["title"], include, exclude)
                and location_matches(j["location"], allowed_locations)
            ]
            print(f"{name:<16} 全部 {len(jobs):>4} 筆 | 符合條件 {len(matches):>3} 筆")
            for j in matches:
                print(f"    - {j['title']}  [{j['location']}]")
            continue

        if not jobs:
            warnings.append(f"{name}: 抓到 0 筆職缺,來源可能有問題")

        matches = [
            j for j in jobs
            if title_matches(j["title"], include, exclude)
            and location_matches(j["location"], allowed_locations)
        ]
        company_seen = set(seen.get(name, []))
        new_jobs = [j for j in matches if j["id"] not in company_seen]
        if new_jobs:
            new_by_company[name] = new_jobs
        # replace this company's state with the current snapshot
        # (jobs that disappeared are pruned automatically)
        seen[name] = sorted(j["id"] for j in matches)

    if check_mode:
        for w in warnings:
            print(f"⚠️  {w}")
        return

    if new_by_company:
        for msg in format_messages(new_by_company, first_run):
            send_telegram(msg)
        total = sum(len(v) for v in new_by_company.values())
        print(f"Sent {total} new job(s) across {len(new_by_company)} company(ies).")
    else:
        print("No new jobs.")

    if warnings:
        send_telegram("⚠️ 機器人警告:\n" + "\n".join(warnings))

    SEEN_PATH.write_text(
        json.dumps(seen, indent=2, ensure_ascii=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
