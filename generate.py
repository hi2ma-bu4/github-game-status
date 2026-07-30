import os
import sys
import argparse
import math
import random
import datetime
import urllib.request
import json
import base64
from io import BytesIO
from PIL import Image

# フォントサブセット化ライブラリ
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
# 2. Font Subsetting Engine (必要文字のみ抽出してBase64化)
# -----------------------------------------------------------------------------
def subset_and_encode_font(font_path, text_to_embed):
    """
    指定された文字(text_to_embed)のみをフォントから抽出(サブセット化)し、
    Base64文字列として返却する
    """
    if not os.path.exists(font_path):
        print(f"Warning: Font file '{font_path}' not found! Falling back to system fonts.")
        return None

    try:
        # 重複文字の排除
        unique_text = "".join(set(text_to_embed))

        # fontTools によるサブセット処理
        font = TTFont(font_path)
        options = Options()
        options.flavor = 'woff'  # 軽量な WOFF 形式に変換
        
        subsetter = Subsetter(options=options)
        subsetter.populate(text=unique_text)
        subsetter.subset(font)

        # メモリ上に WOFF を書き出し
        buf = BytesIO()
        font.save(buf)
        font.close()
        
        # Base64 エンコード
        base64_font = base64.b64encode(buf.getvalue()).decode('utf-8')
        return base64_font
    except Exception as e:
        print(f"Error during font subsetting: {e}")
        return None

# -----------------------------------------------------------------------------
# 3. Logic & Calculations
# -----------------------------------------------------------------------------
JOB_CATEGORIES = {
    '賢者': ['Python', 'JavaScript', 'Ruby', 'PHP', 'Lua', 'Perl', 'Shell', 'R'],
    '魔導士': ['TypeScript', 'Java', 'C#', 'Go', 'Kotlin', 'Swift', 'Scala', 'Dart', 'Haskell'],
    '騎士': ['Dockerfile', 'HCL', 'Nix', 'Yaml', 'Makefile', 'PLpgSQL'],
    '鍛冶師': ['C', 'C++', 'Rust', 'Assembly', 'Zig', 'SystemVerilog']
}

def determine_job(main_lang):
    if not main_lang:
        return "見習い"
    for job, langs in JOB_CATEGORIES.items():
        if any(l.lower() == main_lang.lower() for l in langs):
            return job
    return "勇者"

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
    main_lang = sorted_langs[0][0] if sorted_langs else "なし"
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
        status_effects.append("ゾーン")
    
    if weekday_commits > 0 and (weekend_commits / (weekday_commits + weekend_commits)) > 0.8:
        status_effects.append("過労")

    if agi_stat > 50 and str_stat == 0:
        status_effects.append("透明化")

    inactive_days = 0
    for d in reversed(days):
        if d['contributionCount'] == 0:
            inactive_days += 1
        else:
            break

    if inactive_days >= 365:
        status_effects.append("石化")
    elif inactive_days >= 90:
        status_effects.append("氷結")
    elif inactive_days >= 30:
        status_effects.append("睡眠")

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
# 4. Avatar Pixel Art Generator
# -----------------------------------------------------------------------------
def generate_pixel_avatar_rects(avatar_url, size=16):
    try:
        req = urllib.request.Request(avatar_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as res:
            img_data = res.read()
        
        img = Image.open(BytesIO(img_data)).convert('RGB')
        img_small = img.resize((size, size), Image.Resampling.LANCZOS)
        img_16colors = img_small.quantize(colors=16).convert('RGB')
        
        rects_svg = []
        scale = 6
        
        for y in range(size):
            for x in range(size):
                r, g, b = img_16colors.getpixel((x, y))
                color_hex = f"#{r:02x}{g:02x}{b:02x}"
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
# 5. SVG Renderer & Font Embedding
# -----------------------------------------------------------------------------
def build_svg(data, user_info, avatar_rects, sub_weapon, accessory, font_path):
    status_str = " ".join([f"[{s}]" for s in data['status_effects']]) if data['status_effects'] else "[通常]"
    
    hp_pct = min(1.0, data['hp_cur'] / max(1, data['hp_max']))
    mp_pct = min(1.0, data['mp_cur'] / max(1, data['mp_max']))
    
    username = user_info['name'] if user_info.get('name') else user_info['login']

    # SVG内部で使用する「全文字列」を集約してフォント切り出しを行う
    all_text = (
        f"LV.{data['lv']} {username} 職業:{data['job']} HP MP 通常 状態: {status_str} "
        f"-- 能力値 -- 腕力(PR):{data['str']} 敏捷(CMT):{data['agi']} 知力(REP):{data['int']} "
        f"器用(LNG):{data['dex']} 幸運(STR):{data['luk']} -- 装備 -- "
        f"主武器:{data['main_weapon']} 副武器:{sub_weapon} 装飾品:{accessory} "
        f"{data['hp_cur']}/{data['hp_max']} {data['mp_cur']}/{data['mp_max']}"
    )

    base64_font = subset_and_encode_font(font_path, all_text)

    # フォント埋め込みCSSの生成
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
        # フォントがない場合のフォールバック
        font_face_css = """
        .pixel-text {
          font-family: 'Courier New', monospace;
          font-weight: bold;
          font-size: 12px;
        }
        """

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 320" width="520" height="320">
  <defs>
    <style>
      {font_face_css}

      /* カラー設定 */
      .txt-main {{ fill: #2b1d0c; }}
      .txt-sub  {{ fill: #4a3319; }}
      .txt-badge {{ fill: #8c4a00; }}

      .bg-outer {{ fill: #d8c29d; stroke: #4a3525; stroke-width: 4; }}
      .bg-parchment {{ fill: #f2e3c6; filter: url(#paper-texture); }}
      .panel {{ fill: #edd2a8; stroke: #735338; stroke-width: 2; filter: url(#paper-texture); }}
      .panel-inner {{ fill: #fdf6e7; stroke: #bfa17c; stroke-width: 1; }}
      .bar-bg {{ fill: #c7b08b; stroke: #8c6d53; stroke-width: 1; }}
      .bar-hp {{ fill: #d32f2f; }}
      .bar-mp {{ fill: #1976d2; }}

      /* ダークモード対応 */
      @media (prefers-color-scheme: dark) {{
        .txt-main {{ fill: #e0d0f0; }}
        .txt-sub  {{ fill: #b8a0d0; }}
        .txt-badge {{ fill: #ffb040; }}
        .bg-outer {{ fill: #15121e; stroke: #6b529c; }}
        .bg-parchment {{ fill: #1f1a2e; }}
        .panel {{ fill: #29223d; stroke: #513e78; }}
        .panel-inner {{ fill: #14111f; stroke: #3d305c; }}
        .bar-bg {{ fill: #1a1528; stroke: #453566; }}
        .bar-hp {{ fill: #ff4545; }}
        .bar-mp {{ fill: #3892ff; }}
      }}

      /* ドット単位でカクカク変化するアニメーション */
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

    <filter id="paper-texture" x="0%" y="0%" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="3" result="noise" />
      <feDiffuseLighting in="noise" lighting-color="#ffffff" surfaceScale="1.2" result="light">
        <feDistantLight azimuth="45" elevation="60" />
      </feDiffuseLighting>
      <feBlend mode="multiply" in="SourceGraphic" in2="light" result="blend" />
    </filter>
  </defs>

  <!-- Frame -->
  <rect class="bg-outer" x="4" y="4" width="512" height="312" rx="4" />
  <rect class="bg-parchment" x="8" y="8" width="504" height="304" rx="2" />

  <!-- Header -->
  <rect class="panel" x="16" y="16" width="488" height="40" rx="2" />
  <rect class="panel-inner" x="20" y="20" width="480" height="32" rx="1" />
  <text class="pixel-text txt-main" x="30" y="41">LV.{data['lv']} {username}</text>
  <text class="pixel-text txt-main" x="330" y="41">職業:{data['job']}</text>

  <!-- Avatar & Bars -->
  <rect class="panel" x="16" y="62" width="488" height="112" rx="2" />
  <rect class="panel-inner" x="20" y="66" width="480" height="104" rx="1" />
  
  <g transform="translate(26, 70)">
    {avatar_rects}
  </g>

  <!-- HP Bar -->
  <text class="pixel-text txt-main" x="134" y="91">HP</text>
  <rect class="bar-bg" x="162" y="81" width="180" height="12" rx="1" />
  <rect class="bar-hp" x="162" y="81" width="{int(180 * hp_pct)}" height="12" rx="1" />
  <text class="pixel-text txt-sub" x="350" y="91">{data['hp_cur']}/{data['hp_max']}</text>

  <!-- MP Bar -->
  <text class="pixel-text txt-main" x="134" y="117">MP</text>
  <rect class="bar-bg" x="162" y="107" width="180" height="12" rx="1" />
  <rect class="bar-mp" x="162" y="107" width="{int(180 * mp_pct)}" height="12" rx="1" />
  <text class="pixel-text txt-sub" x="350" y="117">{data['mp_cur']}/{data['mp_max']}</text>

  <!-- Status -->
  <text class="pixel-text txt-badge" x="134" y="152">状態: {status_str}</text>

  <!-- Bottom Left: Stats -->
  <rect class="panel" x="16" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="20" y="184" width="228" height="116" rx="1" />
  <text class="pixel-text txt-main" x="30" y="204">-- 能力値 --</text>
  <text class="pixel-text txt-sub" x="30" y="224">腕力(PR) : {data['str']}</text>
  <text class="pixel-text txt-sub" x="30" y="239">敏捷(CMT): {data['agi']}</text>
  <text class="pixel-text txt-sub" x="30" y="254">知力(REP): {data['int']}</text>
  <text class="pixel-text txt-sub" x="30" y="269">器用(LNG): {data['dex']}</text>
  <text class="pixel-text txt-sub" x="30" y="284">幸運(STR): {data['luk']}</text>

  <!-- Bottom Right: Equipments -->
  <rect class="panel" x="268" y="180" width="236" height="124" rx="2" />
  <rect class="panel-inner" x="272" y="184" width="228" height="116" rx="1" />
  <text class="pixel-text txt-main" x="282" y="204">-- 装備 --</text>
  <text class="pixel-text txt-sub" x="282" y="228">主武器 : {data['main_weapon'][:8]}</text>
  <text class="pixel-text txt-sub" x="282" y="250">副武器 : {sub_weapon[:8]}</text>
  <text class="pixel-text txt-sub" x="282" y="272">装飾品 : {accessory[:8]}</text>
</svg>"""
    return svg

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    parser.add_argument('--username', required=True)
    parser.add_argument('--sub-weapons', default="聖なる剣,盾,魔法の杖,クナイ,伝説の盾")
    parser.add_argument('--accessories', default="指輪,アミュレット,ブーツ,マント")
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

    print(f"Successfully generated {args.output} with embedded subset font!")
