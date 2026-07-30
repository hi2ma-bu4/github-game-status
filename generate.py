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
    created_year = int(data['createdAt'][:4])
    current_year = datetime.datetime.now().year
    lv = max(1, current_year - created_year)

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

    weeks = data['contributionsCollection']['contributionCalendar']['weeks']
    days = [d for w in weeks for d in w['contributionDays']]
    
    last_4_weeks = weeks[-4:] if len(weeks) >= 4 else weeks
    weekly_commits = [sum(d['contributionCount'] for d in w['contributionDays']) for w in last_4_weeks]
    
    this_week_commits = weekly_commits[-1] if weekly_commits else 0
    max_week_commits = max(weekly_commits) if weekly_commits else 1
    if max_week_commits == 0: max_week_commits = 1

    str_stat = data['pullRequests']['totalCount']
    agi_stat = data['contributionsCollection']['totalCommitContributions']
    int_stat = data['contributionsCollection']['totalRepositoryContributions']
    luk_stat = total_stars

    hp_cur = this_week_commits
    hp_max = max_week_commits
    
    mp_cur = min(str_stat, 99)
    mp_max = max(str_stat, 10)

    status_effects = []
    active_days_streak = 0
    for d in reversed(days):
        if d['contributionCount'] > 0:
            active_days_streak += 1
        else:
            break
            
    weekday_commits = 0
    weekend_commits = 0
    for d in days[-30:]:
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
        'hp_cur': hp_cur,
        'hp_max': hp_max,
        'mp_cur': mp_cur,
        'mp_max': mp_max,
        'str': str_stat,
        'agi': agi_stat,
        'int': int_stat,
        'dex': dex,
        'luk': luk_stat,
        'main_weapon': main_lang,
        'status_effects': status_effects
    }

# -----------------------------------------------------------------------------
# 3. Avatar Pixel Art Generator (個別ドットアニメーション対応)
# -----------------------------------------------------------------------------
def generate_pixel_avatar_rects(avatar_url, size=32):
    try:
        req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as res:
            img_data = res.read()
        
        img = Image.open(BytesIO(img_data)).convert('RGB')
        img_small = img.resize((size, size), Image.Resampling.LANCZOS)
        
        rects_svg = []
        scale = 3  # 32x32 -> 96x96
        
        # 左上から右下へのアニメーションディレイ計算用 (最大値: 31 + 31 = 62)
        for y in range(size):
            for x in range(size):
                r, g, b = img_small.getpixel((x, y))
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                
                # 左上(0) -> 右下(2.0秒の間で流れるようにディレイを設定)
                delay = round(((x + y) / (size * 2)) * 1.8, 2)
                
                rects_svg.append(
                    f'<rect class="px-dot" x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}" '
                    f'fill="{color_hex}" style="animation-delay: {delay}s;" />'
                )
        
        return "".join(rects_svg)
    except Exception as e:
        print(f"Failed to process avatar: {e}")
        return '<rect x="0" y="0" width="96" height="96" fill="#555" />'

# -----------------------------------------------------------------------------
# 4. SVG Renderer
# -----------------------------------------------------------------------------
def build_svg(data, user_info, avatar_rects, sub_weapon, accessory):
    status_str = " ".join([f"[{s}]" for s in data['status_effects']]) if data['status_effects'] else "[Normal]"
    
    hp_pct = min(1.0, data['hp_cur'] / max(1, data['hp_max']))
    mp_pct = min(1.0, data['mp_cur'] / max(1, data['mp_max']))
    
    username = user_info['login']

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 320" width="520" height="320">
  <defs>
    <style>
      /* フォントの完全ドット文字（アンチエイリアス無効化）化 */
      .text-main, .text-sub, .status-badge {{
        font-family: 'Courier New', Courier, 'Nimbus Mono L', 'Lucida Console', Monaco, monospace;
        letter-spacing: -0.5px;
        -webkit-font-smoothing: none;
        -moz-osx-font-smoothing: grayscale;
        font-smooth: never;
        text-rendering: pixelated;
        image-rendering: pixelated;
      }}

      .text-main {{
        font-size: 12px;
        font-weight: 900;
        fill: #2b1d0c;
      }}
      .text-sub {{
        font-size: 10px;
        font-weight: 700;
        fill: #4a3319;
      }}
      .status-badge {{
        font-size: 10px;
        font-weight: 700;
        fill: #8c4a00;
      }}

      /* ライトモード */
      .bg-outer {{ fill: #d8c29d; stroke: #4a3525; stroke-width: 4; }}
      .bg-parchment {{ fill: #f2e3c6; filter: url(#paper-texture); }}
      .panel {{ fill: #edd2a8; stroke: #735338; stroke-width: 2; filter: url(#paper-texture); }}
      .panel-inner {{ fill: #fdf6e7; stroke: #bfa17c; stroke-width: 1; }}
      .bar-bg {{ fill: #c7b08b; stroke: #8c6d53; stroke-width: 1; }}
      .bar-hp {{ fill: #d32f2f; }}
      .bar-mp {{ fill: #1976d2; }}

      /* ダークモード */
      @media (prefers-color-scheme: dark) {{
        .bg-outer {{ fill: #15121e; stroke: #6b529c; }}
        .bg-parchment {{ fill: #1f1a2e; }}
        .panel {{ fill: #29223d; stroke: #513e78; }}
        .panel-inner {{ fill: #14111f; stroke: #3d305c; }}
        .text-main {{ fill: #00ffcc; }}
        .text-sub {{ fill: #cbb8ff; }}
        .bar-bg {{ fill: #1a1528; stroke: #453566; }}
        .bar-hp {{ fill: #ff4545; }}
        .bar-mp {{ fill: #3892ff; }}
        .status-badge {{ fill: #ffb703; }}
      }}

      /* 1つ1つのドット(rect)が左上から右下にむけて発光するアニメーション */
      @keyframes dot-flash {{
        0% {{ filter: brightness(1); }}
        15% {{ filter: brightness(2.5) drop-shadow(0px 0px 1px #ffffff); }}
        30% {{ filter: brightness(1); }}
        100% {{ filter: brightness(1); }}
      }}
      .px-dot {{
        animation: dot-flash 4s infinite ease-in-out;
      }}
    </style>

    <!-- ノイズテクスチャフィルター -->
    <filter id="paper-texture" x="0%" y="0%" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="3" result="noise" />
      <feDiffuseLighting in="noise" lighting-color="#ffffff" surfaceScale="1.2" result="light">
        <feDistantLight azimuth="45" elevation="60" />
      </feDiffuseLighting>
      <feBlend mode="multiply" in="SourceGraphic" in2="light" result="blend" />
    </filter>
  </defs>

  <!-- Base Outer Frame -->
  <rect class="bg-outer" x="4" y="4" width="512" height="312" rx="4" />
  <rect class="bg-parchment" x="8" y="8" width="504" height="304" rx="2" />

  <!-- Header Panel -->
  <rect class="panel" x="16" y="16" width="488" height="40" rx="2" />
  <rect class="panel-inner" x="20" y="20" width="480" height="32" rx="1" />
  <text class="text-main" x="30" y="40">Lv.{data['lv']} {username}</text>
  <text class="text-main" x="310" y="40">JOB:{data['job']}</text>

  <!-- Avatar & Bars Panel -->
  <rect class="panel" x="16" y="62" width="488" height="112" rx="2" />
  <rect class="panel-inner" x="20" y="66" width="480" height="104" rx="1" />
  
  <!-- Pixel Avatar (96x96) -->
  <g transform="translate(26, 70)">
    {avatar_rects}
  </g>

  <!-- HP Bar -->
  <text class="text-main" x="134" y="92">HP</text>
  <rect class="bar-bg" x="162" y="81" width="180" height="12" rx="1" />
  <rect class="bar-hp" x="162" y="81" width="{int(180 * hp_pct)}" height="12" rx="1" />
  <text class="text-sub" x="350" y="91">{data['hp_cur']}/{data['hp_max']}</text>

  <!-- MP Bar -->
  <text class="text-main" x="134" y="118">MP</text>
  <rect class="bar-bg" x="162" y="107" width="180" height="12" rx="1" />
  <rect class="bar-mp" x="162" y="107" width="{int(180 * mp_pct)}" height="12" rx="1" />
  <text class="text-sub" x="350" y="117">{data['mp_cur']}/{data['mp_max']}</text>

  <!-- Status Effects -->
  <text class="status-badge" x="134" y="150">STATE: {status_str}</text>

  <!-- Bottom Left Panel: Stats -->
  <rect class="panel" x="16" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="20" y="184" width="228" height="116" rx="1" />
  <text class="text-main" x="28" y="201">-- STATS --</text>

  <text class="text-sub" x="28" y="218">STR(PR)</text>  <text class="text-sub" x="88" y="218">:</text> <text class="text-sub" x="98" y="218">{data['str']}</text>
  <text class="text-sub" x="28" y="234">AGI(CMT)</text> <text class="text-sub" x="88" y="234">:</text> <text class="text-sub" x="98" y="234">{data['agi']}</text>
  <text class="text-sub" x="28" y="250">INT(REP)</text> <text class="text-sub" x="88" y="250">:</text> <text class="text-sub" x="98" y="250">{data['int']}</text>
  <text class="text-sub" x="28" y="266">DEX(LNG)</text> <text class="text-sub" x="88" y="266">:</text> <text class="text-sub" x="98" y="266">{data['dex']}</text>
  <text class="text-sub" x="28" y="282">LUK(STR)</text> <text class="text-sub" x="88" y="282">:</text> <text class="text-sub" x="98" y="282">{data['luk']}</text>

  <!-- Bottom Right Panel: Equipments -->
  <rect class="panel" x="268" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="272" y="184" width="228" height="116" rx="1" />
  <text class="text-main" x="280" y="201">-- EQUIP --</text>

  <text class="text-sub" x="280" y="224">M-WPN</text> <text class="text-sub" x="322" y="224">:</text> <text class="text-sub" x="332" y="224">{data['main_weapon'][:9]}</text>
  <text class="text-sub" x="280" y="248">S-WPN</text> <text class="text-sub" x="322" y="248">:</text> <text class="text-sub" x="332" y="248">{sub_weapon[:9]}</text>
  <text class="text-sub" x="280" y="272">ACC</text>   <text class="text-sub" x="322" y="272">:</text> <text class="text-sub" x="332" y="272">{accessory[:9]}</text>
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
    parser.default="status.svg"
    parser.add_argument('--output', default="status.svg")
    args = parser.parse_args()

    today_str = datetime.datetime.now().strftime('%Y-%m-%d')
    seed_str = f"{args.username}_{today_str}"
    random.seed(seed_str)

    raw_data = fetch_github_data(args.token, args.username)
    status_data = calculate_status(raw_data)

    sub_list = [s.strip() for s in args.sub_weapons.split(',')]
    acc_list = [a.strip() for a in args.accessories.split(',')]
    chosen_sub = random.choice(sub_list)
    chosen_acc = random.choice(acc_list)

    avatar_rects = generate_pixel_avatar_rects(raw_data['avatarUrl'])

    svg_content = build_svg(status_data, raw_data, avatar_rects, chosen_sub, chosen_acc)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    print(f"Successfully generated {args.output} (Seed: {seed_str})")
