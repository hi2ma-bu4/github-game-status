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
# 2. Built-in 5x7 Pixel Font Engine (外部非依存・完全ドット文字)
# -----------------------------------------------------------------------------
PIXEL_FONT = {
    'A': [" █ ", "█ █", "███", "█ █", "█ █"],
    'B': ["██ ", "█ █", "██ ", "█ █", "██ "],
    'C': [" ██", "█  ", "█  ", "█  ", " ██"],
    'D': ["██ ", "█ █", "█ █", "█ █", "██ "],
    'E': ["███", "█  ", "██ ", "█  ", "███"],
    'F': ["███", "█  ", "██ ", "█  ", "█  "],
    'G': [" ██", "█  ", "█ █", "█ █", " ██"],
    'H': ["█ █", "█ █", "███", "█ █", "█ █"],
    'I': ["███", " █ ", " █ ", " █ ", "███"],
    'J': ["  █", "  █", "  █", "█ █", " █ "],
    'K': ["█ █", "██ ", "█  ", "██ ", "█ █"],
    'L': ["█  ", "█  ", "█  ", "█  ", "███"],
    'M': ["█ █", "███", "█ █", "█ █", "█ █"],
    'N': ["█ █", "███", "███", "█ █", "█ █"],
    'O': [" ██", "█ █", "█ █", "█ █", " ██"],
    'P': ["██ ", "█ █", "██ ", "█  ", "█  "],
    'Q': [" ██", "█ █", "█ █", "██ ", " ██"],
    'R': ["██ ", "█ █", "██ ", "█ █", "█ █"],
    'S': [" ██", "█  ", " ██", "  █", "██ "],
    'T': ["███", " █ ", " █ ", " █ ", " █ "],
    'U': ["█ █", "█ █", "█ █", "█ █", " ██"],
    'V': ["█ █", "█ █", "█ █", "█ █", " █ "],
    'W': ["█ █", "█ █", "█ █", "███", "█ █"],
    'X': ["█ █", "█ █", " █ ", "█ █", "█ █"],
    'Y': ["█ █", "█ █", " █ ", " █ ", " █ "],
    'Z': ["███", "  █", " █ ", "█  ", "███"],
    '0': ["███", "█ █", "█ █", "█ █", "███"],
    '1': [" █ ", "██ ", " █ ", " █ ", "███"],
    '2': ["███", "  █", "███", "█  ", "███"],
    '3': ["███", "  █", "███", "  █", "███"],
    '4': ["█ █", "█ █", "███", "  █", "  █"],
    '5': ["███", "█  ", "███", "  █", "███"],
    '6': ["███", "█  ", "███", "█ █", "███"],
    '7': ["███", "  █", "  █", "  █", "  █"],
    '8': ["███", "█ █", "███", "█ █", "███"],
    '9': ["███", "█ █", "███", "  █", "███"],
    ':': ["   ", " █ ", "   ", " █ ", "   "],
    '.': ["   ", "   ", "   ", "   ", " █ "],
    '-': ["   ", "   ", "███", "   ", "   "],
    '[': ["██ ", "█  ", "█  ", "█  ", "██ "],
    ']': [" ██", "  █", "  █", "  █", " ██"],
    '(': ["  █", " █ ", " █ ", " █ ", "  █"],
    ')': ["█  ", " █ ", " █ ", " █ ", "█  "],
    '/': ["  █", "  █", " █ ", "█  ", "█  "],
    ' ': ["   ", "   ", "   ", "   ", "   "]
}

def render_pixel_text(text, x, y, size=2, fill="#2b1d0c"):
    """文字列をピクセルPathとして描画"""
    text = str(text).upper()
    rects = []
    cursor_x = x
    for char in text:
        bitmap = PIXEL_FONT.get(char, PIXEL_FONT[' '])
        for row_idx, row in enumerate(bitmap):
            for col_idx, ch in enumerate(row):
                if ch == '█':
                    rects.append(
                        f'<rect x="{cursor_x + col_idx * size}" y="{y + row_idx * size}" '
                        f'width="{size}" height="{size}" fill="{fill}" />'
                    )
        cursor_x += (len(bitmap[0]) + 1) * size
    return "".join(rects)

# -----------------------------------------------------------------------------
# 3. Logic & Calculations
# -----------------------------------------------------------------------------
JOB_CATEGORIES = {
    'SAGE': ['Python', 'JavaScript', 'Ruby', 'PHP', 'Lua', 'Perl', 'Shell', 'R'],
    'MAGE': ['TypeScript', 'Java', 'C#', 'Go', 'Kotlin', 'Swift', 'Scala', 'Dart', 'Haskell'],
    'KNIGHT': ['Dockerfile', 'HCL', 'Nix', 'Yaml', 'Makefile', 'PLpgSQL'],
    'SMITH': ['C', 'C++', 'Rust', 'Assembly', 'Zig', 'SystemVerilog']
}

def determine_job(main_lang):
    if not main_lang:
        return "NOVICE"
    for job, langs in JOB_CATEGORIES.items():
        if any(l.lower() == main_lang.lower() for l in langs):
            return job
    return "HERO"

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
            lang_sizes[l_name] = lang_sizes.get(l_size, 0) + l_size

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
        status_effects.append("BURNING")
    
    if weekday_commits > 0 and (weekend_commits / (weekday_commits + weekend_commits)) > 0.8:
        status_effects.append("OVERWORK")

    if agi_stat > 50 and str_stat == 0:
        status_effects.append("GHOST")

    inactive_days = 0
    for d in reversed(days):
        if d['contributionCount'] == 0:
            inactive_days += 1
        else:
            break

    if inactive_days >= 365:
        status_effects.append("PETRIFIED")
    elif inactive_days >= 90:
        status_effects.append("FROZEN")
    elif inactive_days >= 30:
        status_effects.append("SLEEP")

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
        'main_weapon': main_lang.upper(),
        'status_effects': status_effects
    }

# -----------------------------------------------------------------------------
# 4. Avatar Pixel Art Generator (16x16, 16色, カクカク高明度アニメ)
# -----------------------------------------------------------------------------
def generate_pixel_avatar_rects(avatar_url, size=16):
    try:
        req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as res:
            img_data = res.read()
        
        img = Image.open(BytesIO(img_data)).convert('RGB')
        img_small = img.resize((size, size), Image.Resampling.LANCZOS)
        
        # 16色へ減色
        img_16colors = img_small.quantize(colors=16).convert('RGB')
        
        rects_svg = []
        scale = 6  # 16x16 -> 96x96
        
        for y in range(size):
            for x in range(size):
                r, g, b = img_16colors.getpixel((x, y))
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                
                # 左上 -> 右下へのカクカクしたステップ遅延
                delay = round(((x + y) / (size * 2)) * 1.5, 2)
                
                rects_svg.append(
                    f'<rect class="px-dot" x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}" '
                    f'fill="{color_hex}" style="animation-delay: {delay}s;" />'
                )
        
        return "".join(rects_svg)
    except Exception as e:
        print(f"Failed to process avatar: {e}")
        return '<rect x="0" y="0" width="96" height="96" fill="#555" />'

# -----------------------------------------------------------------------------
# 5. SVG Renderer
# -----------------------------------------------------------------------------
def build_svg(data, user_info, avatar_rects, sub_weapon, accessory):
    status_str = " ".join([f"[{s}]" for s in data['status_effects']]) if data['status_effects'] else "[NORMAL]"
    
    hp_pct = min(1.0, data['hp_cur'] / max(1, data['hp_max']))
    mp_pct = min(1.0, data['mp_cur'] / max(1, data['mp_max']))
    
    username = user_info['login'].upper()

    # ダークモード対応色定義
    main_text_color = "#2b1d0c"
    sub_text_color = "#4a3319"
    badge_text_color = "#8c4a00"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 320" width="520" height="320">
  <defs>
    <style>
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
        .bar-bg {{ fill: #1a1528; stroke: #453566; }}
        .bar-hp {{ fill: #ff4545; }}
        .bar-mp {{ fill: #3892ff; }}
      }}

      /* ドット単位で「はきはき・カクカク」と明度が切り替わるアニメーション (steps使用) */
      @keyframes dot-flash-sharp {{
        0% {{ filter: brightness(1); }}
        10% {{ filter: brightness(2.8); }}
        20% {{ filter: brightness(1); }}
        100% {{ filter: brightness(1); }}
      }}
      .px-dot {{
        animation: dot-flash-sharp 3s infinite steps(2, start);
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
  {render_pixel_text(f"LV.{data['lv']} {username}", 30, 31, 2, main_text_color)}
  {render_pixel_text(f"JOB:{data['job']}", 310, 31, 2, main_text_color)}

  <!-- Avatar & Bars Panel -->
  <rect class="panel" x="16" y="62" width="488" height="112" rx="2" />
  <rect class="panel-inner" x="20" y="66" width="480" height="104" rx="1" />
  
  <!-- Pixel Avatar (16x16 / 16色制限 / カクカク発光) -->
  <g transform="translate(26, 70)">
    {avatar_rects}
  </g>

  <!-- HP Bar -->
  {render_pixel_text("HP", 134, 82, 2, main_text_color)}
  <rect class="bar-bg" x="162" y="81" width="180" height="12" rx="1" />
  <rect class="bar-hp" x="162" y="81" width="{int(180 * hp_pct)}" height="12" rx="1" />
  {render_pixel_text(f"{data['hp_cur']}/{data['hp_max']}", 350, 83, 1, sub_text_color)}

  <!-- MP Bar -->
  {render_pixel_text("MP", 134, 108, 2, main_text_color)}
  <rect class="bar-bg" x="162" y="107" width="180" height="12" rx="1" />
  <rect class="bar-mp" x="162" y="107" width="{int(180 * mp_pct)}" height="12" rx="1" />
  {render_pixel_text(f"{data['mp_cur']}/{data['mp_max']}", 350, 109, 1, sub_text_color)}

  <!-- Status Effects -->
  {render_pixel_text(f"STATE: {status_str}", 134, 146, 1, badge_text_color)}

  <!-- Bottom Left Panel: Stats -->
  <rect class="panel" x="16" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="20" y="184" width="228" height="116" rx="1" />
  {render_pixel_text("-- STATS --", 28, 194, 2, main_text_color)}

  {render_pixel_text("STR(PR)", 28, 216, 1, sub_text_color)}  {render_pixel_text(":", 92, 216, 1, sub_text_color)} {render_pixel_text(data['str'], 102, 216, 1, sub_text_color)}
  {render_pixel_text("AGI(CMT)", 28, 231, 1, sub_text_color)} {render_pixel_text(":", 92, 231, 1, sub_text_color)} {render_pixel_text(data['agi'], 102, 231, 1, sub_text_color)}
  {render_pixel_text("INT(REP)", 28, 246, 1, sub_text_color)} {render_pixel_text(":", 92, 246, 1, sub_text_color)} {render_pixel_text(data['int'], 102, 246, 1, sub_text_color)}
  {render_pixel_text("DEX(LNG)", 28, 261, 1, sub_text_color)} {render_pixel_text(":", 92, 261, 1, sub_text_color)} {render_pixel_text(data['dex'], 102, 261, 1, sub_text_color)}
  {render_pixel_text("LUK(STR)", 28, 276, 1, sub_text_color)} {render_pixel_text(":", 92, 276, 1, sub_text_color)} {render_pixel_text(data['luk'], 102, 276, 1, sub_text_color)}

  <!-- Bottom Right Panel: Equipments -->
  <rect class="panel" x="268" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="272" y="184" width="228" height="116" rx="1" />
  {render_pixel_text("-- EQUIP --", 280, 194, 2, main_text_color)}

  {render_pixel_text("M-WPN", 280, 220, 1, sub_text_color)} {render_pixel_text(":", 328, 220, 1, sub_text_color)} {render_pixel_text(data['main_weapon'][:9], 338, 220, 1, sub_text_color)}
  {render_pixel_text("S-WPN", 280, 242, 1, sub_text_color)} {render_pixel_text(":", 328, 242, 1, sub_text_color)} {render_pixel_text(sub_weapon.upper()[:9], 338, 242, 1, sub_text_color)}
  {render_pixel_text("ACC",   280, 264, 1, sub_text_color)} {render_pixel_text(":", 328, 264, 1, sub_text_color)} {render_pixel_text(accessory.upper()[:9], 338, 264, 1, sub_text_color)}
</svg>"""
    return svg

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--sub-weapons', default="EXCALIBUR,SHIELD,WAND,KUNAI")
    parser.add_argument('--accessories', default="RING,AMULET,BOOTS")
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

    print(f"Successfully generated {args.output} with pure pixel vector font!")
