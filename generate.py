import os
import sys
import argparse
import math
import random
import datetime
import urllib.request
import json
from io import BytesIO
from PIL import Image

# -----------------------------------------------------------------------------
# 1. GitHub API Data Fetching
# -----------------------------------------------------------------------------
GRAPHQL_URL = "https://api.github.com/graphql"

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    avatarUrl
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
            }
          }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalRepositoryContributions
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
    pullRequests(first: 1) {
      totalCount
    }
  }
}
"""

def fetch_github_data(token, username):
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({'query': GRAPHQL_QUERY, 'variables': {'login': username}}).encode('utf-8'),
        headers={
            'Authorization': f'bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'GitHub-Status-Generator'
        }
    )
    with urllib.request.urlopen(req) as res:
        result = json.loads(res.read().decode('utf-8'))
        if 'errors' in result:
            raise Exception(f"GraphQL Error: {result['errors']}")
        return result['data']['user']

# -----------------------------------------------------------------------------
# 2. Logic & Calculations
# -----------------------------------------------------------------------------
JOB_CATEGORIES = {
    'SAGE': ['Python', 'JavaScript', 'Ruby', 'PHP', 'Lua', 'Perl', 'Shell', 'R'],
    'MAGE': ['TypeScript', 'Java', 'C#', 'Go', 'Kotlin', 'Swift', 'Scala', 'Dart', 'Haskell'],
    'KNIGHT': ['Dockerfile', 'HCL', 'Nix', 'Yaml', 'Makefile', 'PLpgSQL'],
    'SMITH': ['C', 'C++', 'Rust', 'Assembly', 'Zig', 'SystemVerilog']
}

def determine_job(main_lang):
    if not main_lang:
        return "Novice"
    for job, langs in JOB_CATEGORIES.items():
        if any(l.lower() == main_lang.lower() for l in langs):
            if job == 'SAGE': return "賢者"
            if job == 'MAGE': return "魔導士"
            if job == 'KNIGHT': return "騎士"
            if job == 'SMITH': return "鍛冶師"
    return "冒険者"

def calculate_status(data):
    # Lv: アカウント作成年数
    created_year = int(data['createdAt'][:4])
    current_year = datetime.datetime.now().year
    lv = max(1, current_year - created_year)

    # 言語統計 & 総スター数
    lang_sizes = {}
    total_stars = 0
    repos = data['repositories']['nodes']
    for repo in repos:
        total_stars += repo['stargazerCount']
        for edge in repo['languages']['edges']:
            l_name = edge['node']['name']
            l_size = edge['size']
            lang_sizes[l_name] = lang_sizes.get(l_name, 0) + l_size

    sorted_langs = sorted(lang_sizes.items(), key=lambda x: x[1], reverse=True)
    main_lang = sorted_langs[0][0] if sorted_langs else "None"
    dex = len(lang_sizes)

    # コミット・PR履歴解析（カレンダー）
    weeks = data['contributionsCollection']['contributionCalendar']['weeks']
    days = [d for w in weeks for d in w['contributionDays']]
    
    # 過去4週間の計算
    last_4_weeks = weeks[-4:] if len(weeks) >= 4 else weeks
    weekly_commits = [sum(d['contributionCount'] for d in w['contributionDays']) for w in last_4_weeks]
    
    this_week_commits = weekly_commits[-1] if weekly_commits else 0
    max_week_commits = max(weekly_commits) if weekly_commits else 1
    if max_week_commits == 0: max_week_commits = 1

    str_stat = data['pullRequests']['totalCount']
    agi_stat = data['contributionsCollection']['totalCommitContributions']
    int_stat = data['contributionsCollection']['totalRepositoryContributions']
    luk_stat = total_stars

    # 簡易HP/MP（今週コミット数/最大コミット数）
    hp_pct = min(100, int((this_week_commits / max_week_commits) * 100))
    # MPはダミー的にPR数から算出（なければHPと同等）
    mp_pct = min(100, int((str_stat % 10 + 1) * 10))

    # 状態異常の判定
    status_effects = []
    
    # 連続アクティブ日数
    active_days_streak = 0
    for d in reversed(days):
        if d['contributionCount'] > 0:
            active_days_streak += 1
        else:
            break
            
    # 平日 vs 休日コミット比較
    weekday_commits = 0
    weekend_commits = 0
    for d in days[-30:]: # 直近30日
        dt = datetime.datetime.strptime(d['date'], '%Y-%m-%d')
        if dt.weekday() >= 5:
            weekend_commits += d['contributionCount']
        else:
            weekday_commits += d['contributionCount']

    if active_days_streak >= 30:
        status_effects.append("Burning")
    
    if weekday_commits > 0 and (weekend_commits / (weekday_commits + weekend_commits)) > 0.8:
        status_effects.append("Overwork")

    if agi_stat > 50 and str_stat == 0:
        status_effects.append("Ghost")

    # 非アクティブチェック
    inactive_days = 0
    for d in reversed(days):
        if d['contributionCount'] == 0:
            inactive_days += 1
        else:
            break

    if inactive_days >= 365:
        status_effects.append("Petrified")
    elif inactive_days >= 90:
        status_effects.append("Frozen")
    elif inactive_days >= 30:
        status_effects.append("Sleep")

    return {
        'lv': lv,
        'job': determine_job(main_lang),
        'hp_pct': hp_pct,
        'mp_pct': mp_pct,
        'str': str_stat,
        'agi': agi_stat,
        'int': int_stat,
        'dex': dex,
        'luk': luk_stat,
        'main_weapon': main_lang,
        'status_effects': status_effects
    }

# -----------------------------------------------------------------------------
# 3. Avatar Pixel Art Generator (Edge Enhance + Dither + Rect)
# -----------------------------------------------------------------------------
def generate_pixel_avatar_rects(avatar_url, size=32):
    try:
        req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as res:
            img_data = res.read()
        
        img = Image.open(BytesIO(img_data)).convert('RGB')
        
        # 1. リサイズ（小さく）
        img_small = img.resize((size, size), Image.Resampling.BILINEAR)
        
        # 2. 減色 & ディザリング (Web安全色216色へ減色)
        img_pixel = img_small.quantize(colors=16, method=Image.Quantize.MEDIANCUT).convert('RGB')
        
        rects_svg = []
        scale = 3  # 1ピクセルを3x3pxのSVG Rectとして出力
        for y in range(size):
            for x in range(size):
                r, g, b = img_pixel.getpixel((x, y))
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                rects_svg.append(f'<rect x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}" fill="{color_hex}" />')
        
        return "".join(rects_svg)
    except Exception as e:
        print(f"Failed to process avatar: {e}")
        return '<rect x="0" y="0" width="96" height="96" fill="#555" />'

# -----------------------------------------------------------------------------
# 4. SVG Renderer (Light/Dark Mode Support)
# -----------------------------------------------------------------------------
def build_svg(data, user_info, avatar_rects, sub_weapon, accessory):
    status_str = " ".join([f"[{s}]" for s in data['status_effects']]) if data['status_effects'] else "[Normal]"
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 320" width="520" height="320">
  <style>
    .bg {{ fill: #f4f4f6; stroke: #222; stroke-width: 4; }}
    .panel {{ fill: #ffffff; stroke: #333; stroke-width: 2; }}
    .text-main {{ font-family: 'Courier New', monospace; font-weight: bold; fill: #111111; font-size: 14px; }}
    .text-sub {{ font-family: 'Courier New', monospace; fill: #555555; font-size: 12px; }}
    .bar-bg {{ fill: #e0e0e0; }}
    .bar-hp {{ fill: #e53935; }}
    .bar-mp {{ fill: #1e88e5; }}
    .status-badge {{ font-family: 'Courier New', monospace; font-weight: bold; fill: #888888; font-size: 12px; opacity: 0.6; }}

    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #0f0f15; stroke: #e0e0e0; }}
      .panel {{ fill: #181824; stroke: #444466; }}
      .text-main {{ fill: #00ff66; }}
      .text-sub {{ fill: #aaaaff; }}
      .bar-bg {{ fill: #333344; }}
      .bar-hp {{ fill: #ff5252; }}
      .bar-mp {{ fill: #448aff; }}
      .status-badge {{ fill: #ffaa00; opacity: 0.8; }}
    }}
  </style>

  <!-- Outer Window -->
  <rect class="bg" x="4" y="4" width="512" height="312" rx="8" />

  <!-- Header -->
  <rect class="panel" x="16" y="16" width="488" height="40" rx="4" />
  <text class="text-main" x="28" y="41">LV:{data['lv']:02d}  {user_info['login'][:14].upper()}</text>
  <text class="text-main" x="320" y="41">JOB:{data['job']}</text>

  <!-- Avatar & Bars -->
  <rect class="panel" x="16" y="64" width="488" height="112" rx="4" />
  
  <!-- Pixel Avatar (96x96) -->
  <g transform="translate(24, 72)">
    {avatar_rects}
  </g>

  <!-- HP Bar -->
  <text class="text-main" x="132" y="92">HP</text>
  <rect class="bar-bg" x="160" y="80" width="200" height="14" rx="2" />
  <rect class="bar-hp" x="160" y="80" width="{int(200 * data['hp_pct'] / 100)}" height="14" rx="2" />
  <text class="text-sub" x="370" y="92">{data['hp_pct']}%</text>

  <!-- MP Bar -->
  <text class="text-main" x="132" y="122">MP</text>
  <rect class="bar-bg" x="160" y="110" width="200" height="14" rx="2" />
  <rect class="bar-mp" x="160" y="110" width="{int(200 * data['mp_pct'] / 100)}" height="14" rx="2" />
  <text class="text-sub" x="370" y="122">{data['mp_pct']}%</text>

  <!-- Status Effects -->
  <text class="status-badge" x="132" y="155">STATE: {status_str}</text>

  <!-- Bottom Panel Left: Stats -->
  <rect class="panel" x="16" y="184" width="236" height="120" rx="4" />
  <text class="text-main" x="28" y="206">-- STATS --</text>
  <text class="text-sub" x="28" y="228">STR(PR)  : {data['str']}</text>
  <text class="text-sub" x="28" y="246">AGI(CMT) : {data['agi']}</text>
  <text class="text-sub" x="28" y="264">INT(REP) : {data['int']}</text>
  <text class="text-sub" x="28" y="282">DEX(LNG) : {data['dex']}</text>
  <text class="text-sub" x="28" y="300">LUK(STR) : {data['luk']}</text>

  <!-- Bottom Panel Right: Equipments -->
  <rect class="panel" x="268" y="184" width="236" height="120" rx="4" />
  <text class="text-main" x="280" y="206">-- EQUIP --</text>
  <text class="text-sub" x="280" y="232">M-WPN : {data['main_weapon'][:12]}</text>
  <text class="text-sub" x="280" y="258">S-WPN : {sub_weapon[:12]}</text>
  <text class="text-sub" x="280" y="284">ACC   : {accessory[:12]}</text>
</svg>"""
    return svg

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--sub-weapons', default="Excalibur,Shield,Magic Wand,Kunai")
    parser.add_argument('--accessories', default="Ring of Power,Amulet,Hermes Boots")
    parser.add_argument('--output', default="status.svg")
    args = parser.parse_args()

    # シード値の固定: [ユーザーID + YYYY-MM-DD]
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    seed_str = f"{args.username}_{today_str}"
    random.seed(seed_str)

    # データ取得＆計算
    raw_data = fetch_github_data(args.token, args.username)
    status_data = calculate_status(raw_data)

    # ランダム装備の抽選
    sub_list = [s.strip() for s in args.sub_weapons.split(',')]
    acc_list = [a.strip() for a in args.accessories.split(',')]
    chosen_sub = random.choice(sub_list)
    chosen_acc = random.choice(acc_list)

    # アバターのドット絵化
    avatar_rects = generate_pixel_avatar_rects(raw_data['avatarUrl'])

    # SVGのビルド＆出力
    svg_content = build_svg(status_data, raw_data, avatar_rects, chosen_sub, chosen_acc)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    print(f"Successfully generated {args.output} (Seed: {seed_str})")
