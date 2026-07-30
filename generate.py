import os
import sys
import argparse
import math
import random
import datetime
import urllib.request
import json
import base64
import re
from io import BytesIO
from PIL import Image

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options

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
# 2. Dynamic Font Subsetting Engine
# -----------------------------------------------------------------------------
def subset_and_encode_font(font_path, text_to_embed):
    if not os.path.exists(font_path):
        print(f"Warning: Font file '{font_path}' not found! Falling back to system fonts.")
        return None

    try:
        unique_text = "".join(set(text_to_embed))

        font = TTFont(font_path)
        options = Options()
        options.flavor = 'woff'
        
        subsetter = Subsetter(options=options)
        subsetter.populate(text=unique_text)
        subsetter.subset(font)

        buf = BytesIO()
        font.save(buf)
        font.close()
        
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error during font subsetting: {e}")
        return None

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
        'main_weapon': main_lang,
        'status_effects': status_effects
    }

# -----------------------------------------------------------------------------
# 4. Pixel Art Helpers
# -----------------------------------------------------------------------------
def truncate_text(text, max_len=13):
    if len(text) > max_len:
        return text[:max_len-2] + ".."
    return text

def make_pixel_panel(x, y, w, h, corner=4):
    c = corner
    return (
        f"M {x+c} {y} "
        f"H {x+w-c} V {y+c//2} H {x+w-c//2} V {y+c} H {x+w} "
        f"V {y+h-c} H {x+w-c//2} V {y+h-c//2} H {x+w-c} V {y+h} "
        f"H {x+c} V {y+h-c//2} H {x+c//2} V {y+h-c} H {x} "
        f"V {y+c} H {x+c//2} V {y+c//2} H {x+c} Z"
    )

def make_gold_corners(x, y, w, h):
    s = 2
    l = 8
    return f"""
    <path class="gold-decor" d="M {x+2} {y+2} h {l} v {s} h {-l+s} v {l-s} h {-s} Z" />
    <path class="gold-decor" d="M {x+w-2} {y+2} h {-l} v {s} h {l-s} v {l-s} h {s} Z" />
    <path class="gold-decor" d="M {x+2} {y+h-2} h {l} v {-s} h {-l+s} v {-l+s} h {-s} Z" />
    <path class="gold-decor" d="M {x+w-2} {y+h-2} h {-l} v {-s} h {l-s} v {-l+s} h {s} Z" />
    """

PIXEL_HEART_SVG = """
<g transform="translate(0, 0)">
  <path fill="#e53935" d="M2,1 h2 v1 h-2 Z M6,1 h2 v1 h-2 Z M1,2 h4 v1 h-4 Z M5,2 h4 v1 h-4 Z M1,3 h8 v1 h-8 Z M2,4 h6 v1 h-6 Z M3,5 h4 v1 h-4 Z M4,6 h2 v1 h-2 Z" />
  <path fill="#ffffff" d="M2,2 h1 v1 h-1 Z" opacity="0.8" />
</g>
"""

PIXEL_POTION_SVG = """
<g transform="translate(0, 0)">
  <path fill="#1e88e5" d="M3,0 h3 v1 h-3 Z M3,1 h3 v1 h-3 Z M2,2 h5 v1 h-5 Z M1,3 h7 v1 h-7 Z M1,4 h7 v1 h-7 Z M2,5 h5 v1 h-5 Z M3,6 h3 v1 h-3 Z" />
  <path fill="#90caf9" d="M2,3 h1 v2 h-1 Z" opacity="0.9" />
</g>
"""

def get_status_icon(effect):
    if effect == "BURNING":
        return '<path fill="#ff7043" d="M3,0 h2 v1 h-2 Z M2,1 h4 v1 h-4 Z M1,2 h6 v1 h-6 Z M0,3 h8 v3 h-8 Z M1,6 h6 v1 h-6 Z M2,7 h4 v1 h-4 Z"/>'
    elif effect == "FROZEN":
        return '<path fill="#29b6f6" d="M3,0 h2 v8 h-2 Z M0,3 h8 v2 h-8 Z M1,1 h6 v6 h-6 Z"/>'
    elif effect == "SLEEP":
        return '<path fill="#ab47bc" d="M1,0 h6 v2 h-4 l4,4 v2 h-6 v-2 h4 l-4,-4 Z"/>'
    elif effect == "OVERWORK":
        return '<path fill="#ffee58" d="M2,0 h4 v2 h-4 Z M0,2 h8 v4 h-8 Z M2,6 h4 v2 h-4 Z"/>'
    elif effect == "GHOST":
        return '<path fill="#b0bec5" d="M2,0 h4 v1 h-4 Z M1,1 h6 v5 h-6 Z M1,6 h2 v2 h-2 Z M5,6 h2 v2 h-2 Z"/>'
    else:
        return '<path fill="#66bb6a" d="M3,0 h2 v2 h-2 Z M0,3 h8 v2 h-8 Z M3,6 h2 v2 h-2 Z"/>'

# -----------------------------------------------------------------------------
# 5. Avatar Pixel Art Generator (アバター＆銀縁生成)
# -----------------------------------------------------------------------------
def generate_pixel_avatar_rects(avatar_url, size=16):
    try:
        req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as res:
            img_data = res.read()
        
        img = Image.open(BytesIO(img_data)).convert('RGB')
        img_small = img.resize((size, size), Image.Resampling.LANCZOS)
        img_16colors = img_small.quantize(colors=16).convert('RGB')
        
        avatar_dots_svg = []
        scale = 5  # 16 * 5 = 80px
        
        # 1. アバター画像（ドット）
        for y in range(size):
            for x in range(size):
                r, g, b = img_16colors.getpixel((x, y))
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
                delay = round(((x + y) / (size * 2)) * 1.5, 2)
                
                avatar_dots_svg.append(
                    f'<rect class="px-dot" x="{x*scale}" y="{y*scale}" width="{scale}" height="{scale}" '
                    f'fill="{color_hex}" style="animation-delay: {delay}s;" />'
                )
        
        # 2. 銀縁フレーム（外枠と内光沢）
        silver_frame_path = make_pixel_panel(-2, -2, size*scale + 4, size*scale + 4, corner=3)
        silver_inner_path = make_pixel_panel(0, 0, size*scale, size*scale, corner=2)
        
        return f'''
        <!-- 背景ベース -->
        <path fill="#1a120b" d="{silver_frame_path}" />
        
        <!-- アバター画像 -->
        <g>
          {"".join(avatar_dots_svg)}
        </g>
        
        <!-- アイコンにぴったり重なる最前面の銀縁 -->
        <path fill="none" stroke="#c0c0c0" stroke-width="2" d="{silver_frame_path}" />
        <path fill="none" stroke="#ffffff" stroke-width="1" d="{silver_inner_path}" opacity="0.6" />
        '''
    except Exception as e:
        print(f"Failed to process avatar: {e}")
        return '<rect x="0" y="0" width="80" height="80" fill="#555" />'

# -----------------------------------------------------------------------------
# 6. SVG Renderer & Automated Font Embedding
# -----------------------------------------------------------------------------
def build_svg(data, user_info, avatar_rects, sub_weapon, accessory, font_path):
    first_effect = data['status_effects'][0] if data['status_effects'] else "NORMAL"
    status_str = " ".join([f"[{s}]" for s in data['status_effects']]) if data['status_effects'] else "[NORMAL]"
    status_icon_svg = get_status_icon(first_effect)

    hp_pct = min(1.0, data['hp_cur'] / max(1, data['hp_max']))
    mp_pct = min(1.0, data['mp_cur'] / max(1, data['mp_max']))
    
    display_name = user_info['name'] if user_info.get('name') else user_info['login']
    login_id = user_info['login']

    p_header_out = make_pixel_panel(16, 16, 488, 40, 4)
    p_header_in  = make_pixel_panel(20, 20, 480, 32, 2)

    p_mid_out    = make_pixel_panel(16, 62, 488, 112, 4)
    p_mid_in     = make_pixel_panel(20, 66, 480, 104, 2)

    p_btm_l_out  = make_pixel_panel(16, 180, 236, 124, 4)
    p_btm_l_in   = make_pixel_panel(20, 184, 228, 116, 2)

    p_btm_r_out  = make_pixel_panel(268, 180, 236, 124, 4)
    p_btm_r_in   = make_pixel_panel(272, 184, 228, 116, 2)

    gold_h   = make_gold_corners(20, 20, 480, 32)
    gold_m   = make_gold_corners(20, 66, 480, 104)
    gold_bl  = make_gold_corners(20, 184, 228, 116)
    gold_br  = make_gold_corners(272, 184, 228, 116)

    m_wpn_str = truncate_text(data['main_weapon'], 13)
    s_wpn_str = truncate_text(sub_weapon, 13)
    acc_str   = truncate_text(accessory, 13)

    status_aura_class = f"aura-{first_effect.lower()}"

    raw_svg_text = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 320" width="520" height="320">
  <defs>
    <!-- ノイズフィルター -->
    <filter id="bg-noise" x="0%" y="0%" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="3" result="noise" />
      <feColorMatrix type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.07 0" />
      <feComposite operator="in" in2="SourceGraphic" />
    </filter>

    <!-- UIパネルグラデーション -->
    <linearGradient id="panel-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#3d2d1d" />
      <stop offset="100%" stop-color="#241a10" />
    </linearGradient>

    <linearGradient id="panel-grad-dark" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#201a2e" />
      <stop offset="100%" stop-color="#120e1c" />
    </linearGradient>

    <!-- HP/MP 流動アニメーション用グラデーション -->
    <linearGradient id="hp-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#d32f2f" />
      <stop offset="30%" stop-color="#ff6666" />
      <stop offset="60%" stop-color="#d32f2f" />
      <stop offset="100%" stop-color="#9a0007" />
    </linearGradient>

    <linearGradient id="mp-grad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#1976d2" />
      <stop offset="30%" stop-color="#64b5f6" />
      <stop offset="60%" stop-color="#1976d2" />
      <stop offset="100%" stop-color="#004ba0" />
    </linearGradient>

    <style>
      /*FONT_PLACEHOLDER*/

      .txt-main {{ fill: #f2e3c6; }}
      .txt-sub  {{ fill: #d8c29d; }}
      .txt-id   {{ fill: #bfa882; font-size: 10px; }}
      .txt-badge {{ fill: #ffb040; }}

      .bg-outer {{ fill: #4a3525; stroke: #2b1d0c; stroke-width: 2; }}
      .bg-parchment {{ fill: #d8c29d; transition: fill 0.5s ease; }}
      .bg-noise-layer {{ fill: #000000; filter: url(#bg-noise); }}

      .panel-outer {{ fill: #8c6d53; }}
      .panel-inner {{ fill: url(#panel-grad); }}
      .gold-decor  {{ fill: #f5d061; }}
      
      .bar-bg {{ fill: #140d07; stroke: #5c4533; stroke-width: 1; }}

      .bar-hp {{ fill: url(#hp-grad); }}
      .bar-mp {{ fill: url(#mp-grad); }}
      
      /* -------------------------------------------------- */
      /* 多彩なオーラ・ステータス演出                       */
      /* -------------------------------------------------- */
      
      /* [BURNING] 火炎オーラ */
      @keyframes aura-burn-frame {{
        0% {{ stroke: #ff3300; filter: drop-shadow(0 0 2px #ff3300); }}
        50% {{ stroke: #ff9900; filter: drop-shadow(0 0 8px #ff5500); }}
        100% {{ stroke: #ff3300; filter: drop-shadow(0 0 2px #ff3300); }}
      }}
      .aura-burning {{
        animation: aura-burn-frame 1.2s infinite alternate;
        stroke-width: 2px !important;
      }}

      /* [FROZEN] 凍結シマー */
      @keyframes aura-freeze-frame {{
        0% {{ stroke: #00d2ff; filter: drop-shadow(0 0 2px #00d2ff); }}
        50% {{ stroke: #e0f7fa; filter: drop-shadow(0 0 6px #80e5ff); }}
        100% {{ stroke: #00d2ff; filter: drop-shadow(0 0 2px #00d2ff); }}
      }}
      .aura-frozen {{
        animation: aura-freeze-frame 2.5s infinite alternate;
        stroke-width: 2px !important;
      }}

      /* [OVERWORK] 過負荷・パルス */
      @keyframes aura-overwork-frame {{
        0% {{ stroke: #ffee58; opacity: 1; }}
        20% {{ stroke: #f57f17; opacity: 0.6; }}
        40% {{ stroke: #ffee58; opacity: 1; }}
        100% {{ stroke: #f57f17; opacity: 0.8; }}
      }}
      .aura-overwork {{
        animation: aura-overwork-frame 0.8s infinite steps(2, start);
        stroke-width: 2px !important;
      }}

      /* [GHOST/SLEEP] 幽幻・静寂 */
      @keyframes aura-ghost-frame {{
        0% {{ stroke: #b0bec5; filter: drop-shadow(0 0 2px #78909c); }}
        100% {{ stroke: #78909c; filter: drop-shadow(0 0 5px #b0bec5); }}
      }}
      .aura-ghost, .aura-sleep {{
        animation: aura-ghost-frame 3s infinite alternate;
        stroke-width: 1.5px !important;
      }}

      /* ダークモード対応 */
      @media (prefers-color-scheme: dark) {{
        .txt-main {{ fill: #e0d0f0; }}
        .txt-sub  {{ fill: #b8a0d0; }}
        .txt-id   {{ fill: #8a70a0; }}
        .txt-badge {{ fill: #ffcc00; }}
        
        .bg-outer {{ fill: #100d17; stroke: #3d305c; }}
        .bg-parchment {{ fill: #1c1626; }}
        
        .panel-outer {{ fill: #513e78; }}
        .panel-inner {{ fill: url(#panel-grad-dark); }}
        .gold-decor  {{ fill: #ffb040; }}
        
        .bar-bg {{ fill: #0a0810; stroke: #3d305c; }}
      }}

      @keyframes dot-flash-sharp {{
        0% {{ filter: brightness(1); }}
        10% {{ filter: brightness(2.5); }}
        20% {{ filter: brightness(1); }}
        100% {{ filter: brightness(1); }}
      }}
      .px-dot {{
        animation: dot-flash-sharp 3s infinite steps(2, start);
      }}
    </style>
  </defs>

  <!-- Background -->
  <rect class="bg-outer" x="4" y="4" width="512" height="312" />
  <rect class="bg-parchment" x="8" y="8" width="504" height="304" />
  <rect class="bg-noise-layer" x="8" y="8" width="504" height="304" />

  <!-- Header -->
  <path class="panel-outer {status_aura_class}" d="{p_header_out}" />
  <path class="panel-inner" d="{p_header_in}" />
  {gold_h}
  <text class="pixel-text txt-main" x="30" y="41">Lv.{data['lv']} {display_name} <tspan class="txt-id">({login_id})</tspan></text>
  <text class="pixel-text txt-main" x="350" y="41">JOB:{data['job']}</text>

  <!-- Avatar & Bars Panel -->
  <path class="panel-outer {status_aura_class}" d="{p_mid_out}" />
  <path class="panel-inner" d="{p_mid_in}" />
  {gold_m}
  
  <!-- Avatar  -->
  <g transform="translate(32, 78)">
    {avatar_rects}
  </g>

  <!-- HP Bar + Heart Icon -->
  <g transform="translate(134, 83)">
    {PIXEL_HEART_SVG}
  </g>
  <text class="pixel-text txt-main" x="146" y="91">HP</text>
  <rect class="bar-bg" x="170" y="81" width="172" height="12" />
  <svg x="170" y="81" width="172" height="12">
    <rect class="bar-hp" x="0" y="0" width="{int(172 * hp_pct)}" height="12" />
  </svg>
  <text class="pixel-text txt-sub" x="350" y="91">{data['hp_cur']}/{data['hp_max']}</text>

  <!-- MP Bar + Potion Icon -->
  <g transform="translate(134, 109)">
    {PIXEL_POTION_SVG}
  </g>
  <text class="pixel-text txt-main" x="146" y="117">MP</text>
  <rect class="bar-bg" x="170" y="107" width="172" height="12" />
  <svg x="170" y="107" width="172" height="12">
    <rect class="bar-mp" x="0" y="0" width="{int(172 * mp_pct)}" height="12" />
  </svg>
  <text class="pixel-text txt-sub" x="350" y="117">{data['mp_cur']}/{data['mp_max']}</text>

  <!-- Status + Status Effect Icon -->
  <g transform="translate(134, 142)">
    <svg width="8" height="8" viewBox="0 0 8 8">
      {status_icon_svg}
    </svg>
  </g>
  <text class="pixel-text txt-badge" x="146" y="150">STATE: {status_str}</text>

  <!-- Bottom Left: Stats -->
  <path class="panel-outer {status_aura_class}" d="{p_btm_l_out}" />
  <path class="panel-inner" d="{p_btm_l_in}" />
  {gold_bl}
  <text class="pixel-text txt-main" x="30" y="204">-- STATS --</text>
  <text class="pixel-text txt-sub" x="30" y="224">STR(PR)</text>  <text class="pixel-text txt-sub" x="102" y="224">: {data['str']}</text>
  <text class="pixel-text txt-sub" x="30" y="239">AGI(CMT)</text> <text class="pixel-text txt-sub" x="102" y="239">: {data['agi']}</text>
  <text class="pixel-text txt-sub" x="30" y="254">INT(REP)</text> <text class="pixel-text txt-sub" x="102" y="254">: {data['int']}</text>
  <text class="pixel-text txt-sub" x="30" y="269">DEX(LNG)</text> <text class="pixel-text txt-sub" x="102" y="269">: {data['dex']}</text>
  <text class="pixel-text txt-sub" x="30" y="284">LUK(STR)</text> <text class="pixel-text txt-sub" x="102" y="284">: {data['luk']}</text>

  <!-- Bottom Right: Equipments -->
  <path class="panel-outer {status_aura_class}" d="{p_btm_r_out}" />
  <path class="panel-inner" d="{p_btm_r_in}" />
  {gold_br}
  <text class="pixel-text txt-main" x="282" y="204">-- EQUIP --</text>
  <text class="pixel-text txt-sub" x="282" y="228">M-WPN</text> <text class="pixel-text txt-sub" x="338" y="228">: {m_wpn_str}</text>
  <text class="pixel-text txt-sub" x="282" y="250">S-WPN</text> <text class="pixel-text txt-sub" x="338" y="250">: {s_wpn_str}</text>
  <text class="pixel-text txt-sub" x="282" y="272">ACC</text>   <text class="pixel-text txt-sub" x="338" y="272">: {acc_str}</text>
</svg>"""

    # --- フォント自動抽出処理 ---
    extracted_text_nodes = re.findall(r'<text[^>]*>(.*?)</text>', raw_svg_text, re.DOTALL)
    extracted_all_characters = "".join(extracted_text_nodes)

    base64_font = subset_and_encode_font(font_path, extracted_all_characters)

    if base64_font:
        font_face_css = f"""
        @font-face {{
          font-family: 'PixelCustomFont';
          src: url('data:font/woff;charset=utf-8;base64,{base64_font}') format('woff');
          font-weight: normal;
          font-style: normal;
        }}
        .pixel-text {{
          font-family: 'PixelCustomFont', monospace;
          font-size: 12px;
          image-rendering: pixelated;
        }}
        """
    else:
        font_face_css = """
        .pixel-text {
          font-family: 'Courier New', monospace;
          font-weight: bold;
          font-size: 12px;
        }
        """

    return raw_svg_text.replace("/*FONT_PLACEHOLDER*/", font_face_css)

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--sub-weapons', default="Aegis Shield,Magic Wand,Kunai,Holy Bible,Master Sword")
    parser.add_argument('--accessories', default="Ring of Power,Amulet of Life,Hermes Boots,Pendant of Wisdom")
    parser.add_argument('--font-path', default="font.ttf")
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

    svg_content = build_svg(status_data, raw_data, avatar_rects, chosen_sub, chosen_acc, args.font_path)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(svg_content)

    print(f"Successfully generated {args.output} with layered avatar and enhanced status auras!")
