# ponytail: one check - ranking must not be a duration proxy, must not pool
# platforms, and must stay silent when the gaps are noise. Frozen fixture
# (the WS_13.08 4-clip snapshot that motivated the fix) - NOT the live log,
# which grows and broke the premise assertions once a real standout landed.
import sys
sys.path.insert(0, "scripts/publish")
import scrape

rows = [
    {"platform": "tiktok", "clip": "clip-4", "hook": "אילון", "duration": 32.22,
     "views": 734, "avg_watch_s": 13.9, "watched_full": 17.6, "retention": 43},
    {"platform": "tiktok", "clip": "clip-15", "hook": "אודיסאה", "duration": 33.3,
     "views": 1400, "avg_watch_s": 13.41, "watched_full": 17.0, "retention": 40},
    {"platform": "tiktok", "clip": "clip-13", "hook": "GTM", "duration": 35.8,
     "views": 1200, "avg_watch_s": 13.2, "watched_full": 18.9, "retention": 37},
    {"platform": "tiktok", "clip": "clip-14", "hook": "אופנהיימר", "duration": 43.34,
     "views": 1100, "avg_watch_s": 6.18, "watched_full": 3.4, "retention": 14},
    {"platform": "instagram", "clip": "clip-15", "hook": "אודיסאה", "duration": 33.3,
     "views": 7182, "avg_watch_s": 3, "retention": 9},
    {"platform": "instagram", "clip": "clip-4", "hook": "אילון", "duration": 32.22,
     "views": 1858, "avg_watch_s": 2, "retention": 6},
    {"platform": "instagram", "clip": "clip-14", "hook": "אופנהיימר", "duration": 43.34,
     "views": 1339, "avg_watch_s": 2, "retention": 5},
    {"platform": "instagram", "clip": "clip-13", "hook": "GTM", "duration": 35.8,
     "views": 991, "avg_watch_s": 3, "retention": 8},
]
tt, ig = scrape._rank(rows, "tiktok"), scrape._rank(rows, "instagram")
best, worst = scrape._outliers(tt, "tiktok")

print("TikTok (avg_watch_s):")
for r in tt: print(f"  {r['clip']:<8} {r['avg_watch_s']:>6}s dur={r['duration']:<6} views={r['views']:<5} ret={r['retention']}%")
print("Instagram (views):")
for r in ig: print(f"  {r['clip']:<8} views={r['views']:<5} watch={r['avg_watch_s']}s ret={r['retention']}%")
print(f"\nbest  -> {best['clip'] if best else None}")
print(f"worst -> {worst['clip'] if worst else None}")

# 1. platforms never pooled
assert {r["platform"] for r in tt} == {"tiktok"}
assert {r["platform"] for r in ig} == {"instagram"}

# 2. premise: old retention order was exactly shortest-first
old = sorted((r for r in rows if r.get("platform")=="tiktok" and r.get("retention") is not None),
             key=lambda r: r["retention"], reverse=True)
by_dur = sorted((r for r in rows if r.get("platform")=="tiktok" and r.get("retention") is not None),
                key=lambda r: r["duration"])
assert [r["clip"] for r in old] == [r["clip"] for r in by_dur] == ["clip-4","clip-15","clip-13","clip-14"]

# 3. THE FIX: no winner is declared off a 0.7s spread, even though clip-4 sorts first
assert best is None, f"named a winner on noise: {best}"

# 4. but the real collapse is still reported
assert worst and worst["clip"] == "clip-14"
assert worst["avg_watch_s"] < tt[0]["avg_watch_s"] / 2

# 5. a genuine standout IS reported (synthetic: clip-99 doubles the median)
spike = rows + [{"platform":"tiktok","clip":"clip-99","avg_watch_s":30.0,
                 "duration":35,"views":9000,"retention":86,"watched_full":40,"hook":"x"}]
b2, w2 = scrape._outliers(scrape._rank(spike,"tiktok"), "tiktok")
assert b2 and b2["clip"] == "clip-99", f"missed a real standout: {b2}"
assert w2 and w2["clip"] == "clip-14"

# 6. too few rows to judge -> silent
assert scrape._outliers(tt[:2], "tiktok") == (None, None)

# 7. IG ranks on views; its watch time has no resolution to rank on
assert ig[0]["clip"] == "clip-15" and len({r["avg_watch_s"] for r in ig}) <= 2

print("\nall assertions passed")

# YT Studio analytics parser: label-anchored text extraction, M:SS -> seconds.
yt_body = """Overview
Views
1,204
Watch time (hours)
5.4
Average view duration
0:16
Viewed vs. swiped away
71.3%
"""
ytm = scrape._extract_yt_metrics(yt_body)
assert ytm == {"views": 1204, "avg_watch_s": 16, "watched_full": 71.3}, ytm
assert scrape._extract_yt_metrics("no analytics here") is None
assert scrape.RANK_BY["youtube"] == "avg_watch_s"
print("youtube parser ok")

# LinkedIn author-view parser: impressions -> views, reactions/comments best-effort.
li_body = """Navot Volk
בניתי כלי שחותך קליפים
1,204 impressions
View analytics
57 reactions
12 comments
"""
lim = scrape._extract_li_metrics(li_body)
assert lim == {"views": 1204, "reactions": 57, "comments": 12}, lim
assert scrape._extract_li_metrics("no metrics here") is None
assert scrape.RANK_BY["linkedin"] == "views"
print("linkedin parser ok")

# TikTok advanced text parsing: traffic split + drop point ride on the overview.
tt_body = """Video views
560
Average watch time
12.78s
Watched full video
19.5%
Most viewers stopped watching at 0:02. Play the video below.
Traffic source
For You
97.5%
Personal profile
2.3%
Following
<0.1%
Search
<0.1%
"""
ttm = scrape._extract_metrics(tt_body)
assert ttm["views"] == 560 and ttm["avg_watch_s"] == 12.78, ttm
assert ttm["drop_at_s"] == 2, ttm
assert ttm["traffic"]["for_you"] == 97.5 and ttm["traffic"]["search"] == 0.0, ttm

# IG follower split + follows.
ig_modal = "0:03\nViews\nViews\n989\nFollowers\n15.6%\nNon-followers\n84.4%\nLikes\n2\nSaves\n0\nShares\n3\nFollows\n1\n"
igm = scrape._extract_ig_metrics(ig_modal)
assert igm["views"] == 989 and igm["nonfollower_pct"] == 84.4, igm
assert igm["shares"] == 3 and igm["follows"] == 1, igm

# TikTok insight-JSON miner: retention curve + share/save counts.
import json as _json
ins = _json.dumps({"video_retention_rate_realtime": {"value": {"list": [
    {"timestamp": 0, "value": 1.0}, {"timestamp": 1000, "value": 0.712},
    {"timestamp": 2000, "value": 0.55031}]}}, "share_count": 4, "collect_count": 2})
ex = scrape._tt_insight_extras(ins)
assert ex["retention_curve"] == [[0, 100.0], [1, 71.2], [2, 55.0]], ex
ins3 = _json.dumps({"video_retention_rate_realtime": {"value": {"list": [
    {"timestamp": 0, "value": 1.0}, {"timestamp": 3000, "value": 0.57}]}}})
assert scrape._tt_insight_extras(ins3)["hook_hold_3s"] == 57.0
assert ex["shares"] == 4 and ex["saves"] == 2, ex
print("advanced analytics parsers ok")
