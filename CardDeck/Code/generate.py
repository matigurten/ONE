from PIL import Image, ImageDraw, ImageFont
import os
import re
import math
import random

# --- Config ---
WIDTH, HEIGHT = 600, 600
BG_COLOR = (255, 255, 255)
BORDER_WIDTH = 12
OUTPUT_DIR = "output"
FONT_PATH = "/usr/share/fonts/liberation-fonts/LiberationSans-Bold.ttf"
SYMBOL_FONT_PATH = "/run/host/fonts/google-noto/NotoSansSymbols2-Regular.ttf"
RULES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.md")

COLOR_MAP = {
    "BLACK": (0, 0, 0),
    "WHITE": (255, 255, 255),
    "RED":   (220, 30, 30),
    "GREEN": (30, 160, 30),
    "BLUE":  (30, 80, 220),
    "GRAY":  (120, 120, 120),
    "GREY":  (120, 120, 120),
}

def parse_color(s):
    s = s.strip().upper()
    if s in COLOR_MAP:
        return COLOR_MAP[s]
    m = re.match(r'#([0-9A-Fa-f]{6})', s)
    if m:
        h = m.group(1)
        return (int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))
    return (0, 0, 0)

# --- Parse rules.md ---
def parse_rules(path=RULES_PATH):
    with open(path) as f:
        content = f.read()

    suits_section = re.search(r'## Suits\n(.*?)(?=##|\Z)', content, re.DOTALL).group(1)
    suits = []
    for m in re.finditer(
            r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|',
            suits_section
    ):
        name      = m.group(1).strip()
        label     = m.group(2).strip()
        symbol    = m.group(3).strip()
        color_str = m.group(4).strip()
        if re.match(r'^[-\s]+$', name) or name.lower() == 'name':
            continue
        is_triangle = name.lower() == "triangle" or "rgb" in color_str.lower()
        color = (0, 0, 0) if is_triangle else parse_color(color_str.split()[0])
        suits.append({"name": name, "label": label, "symbol": symbol,
                      "color": color, "is_triangle": is_triangle})

    ranks_section = re.search(r'## Ranks.*?\n(.*?)(?=##|\Z)', content, re.DOTALL).group(1)
    ranks = []
    for m in re.finditer(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', ranks_section):
        val_str, label = m.group(1).strip(), m.group(2).strip()
        range_match = re.match(r'(\d+)[–\-](\d+)', val_str)
        if range_match:
            for v in range(int(range_match.group(1)), int(range_match.group(2))+1):
                ranks.append((v, str(v)))
        else:
            try:
                ranks.append((int(val_str), label))
            except ValueError:
                pass

    specials_section = re.search(r'## Special Cards\n(.*?)(?=##|\Z)', content, re.DOTALL).group(1)
    specials = []
    for m in re.finditer(r'\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|', specials_section):
        name, count = m.group(1).strip(), int(m.group(2))
        if re.match(r'^[-\s]+$', name) or name.lower() == 'name':
            continue
        specials.append({"name": name, "count": count})

    return suits, ranks, specials

# --- Fonts ---
def load_fonts():
    try:
        font_large   = ImageFont.truetype(FONT_PATH, 80)
        font_special = ImageFont.truetype(FONT_PATH, 100)
    except OSError:
        font_large = font_special = ImageFont.load_default()
    try:
        font_pip = ImageFont.truetype(SYMBOL_FONT_PATH, 60)
    except OSError:
        font_pip = ImageFont.load_default()
    return font_large, font_pip, font_special

# --- Hexagon ---
def hex_points(cx, cy, r, flat_top=True):
    pts = []
    for i in range(6):
        angle = math.radians(60 * i) if flat_top else math.radians(30 + 60 * i)
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return pts

def mask_hex(img):
    """White out everything outside the hexagon."""
    cx, cy = WIDTH // 2, HEIGHT // 2
    r = min(WIDTH, HEIGHT) // 2 - BORDER_WIDTH // 2
    pts = hex_points(cx, cy, r, flat_top=True)
    mask = Image.new("L", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    inv_mask = mask.point(lambda x: 255 - x)
    white = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    img.paste(white, mask=inv_mask)

def make_border(img, color):
    draw = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2, HEIGHT // 2
    r = min(WIDTH, HEIGHT) // 2 - BORDER_WIDTH // 2
    pts = hex_points(cx, cy, r, flat_top=True)
    draw.line(pts + [pts[0]], fill=color, width=BORDER_WIDTH)

def make_triangle_border(img):
    draw = ImageDraw.Draw(img)
    cx, cy = WIDTH // 2, HEIGHT // 2
    r = min(WIDTH, HEIGHT) // 2 - BORDER_WIDTH // 2
    pts = hex_points(cx, cy, r, flat_top=True)
    colors = [(220,30,30),(220,30,30),(30,160,30),(30,160,30),(30,80,220),(30,80,220)]
    for i in range(6):
        draw.line([pts[i], pts[(i+1)%6]], fill=colors[i], width=BORDER_WIDTH)

# --- Triangle symbol ---
def draw_triangle_symbol(img, cx, cy, size=180):
    h = int(size * math.sqrt(3) / 2)
    top   = (cx, cy - h * 2 // 3)
    left  = (cx - size // 2, cy + h // 3)
    right = (cx + size // 2, cy + h // 3)
    draw = ImageDraw.Draw(img)
    draw.polygon([top, left, right], fill=(0, 0, 0))
    ew = 8
    draw.line([top, left],   fill=(220, 30, 30),  width=ew)
    draw.line([left, right], fill=(30, 80, 220),   width=ew)
    draw.line([right, top],  fill=(30, 160, 30),   width=ew)

# --- Sacred geometry pip layout ---
def sacred_pip_positions(value, cx, cy, r_hex):
    r_outer = r_hex * 0.60   # outer ring: 6 pips
    r_inner = r_hex * 0.28   # inner ring: recursive 1-6
    wobble  = 30

    def ring(n, radius, offset_deg=0):
        pts = []
        for i in range(n):
            angle = math.radians(offset_deg + 360 * i / n - 90)
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            pts.append((x, y, random.uniform(-wobble, wobble)))
        return pts

    # Each shell: n pips on a ring, radius proportional to n
    # Shells fill from outside in: first shell=6, second=5, third=4...
    # Each shell rotated 30° more than the previous
    # pip_r(n) = ring radius for n pips — proportional so they don't crowd
    def pip_r(n):
        # Shells 1-8, each with distinct radius, 8 near the border
        radii = {1: 0, 2: 0.12, 3: 0.20, 4: 0.28, 5: 0.37, 6: 0.46, 7: 0.55, 8: 0.64}
        return r_hex * radii.get(n, 0)

    def make_shell(n, rotation_offset=0):
        if n == 1:
            return [(cx, cy, random.uniform(-wobble, wobble))]
        pts = []
        for i in range(n):
            angle = math.radians(360 * i / n - 90 + rotation_offset)
            x = cx + pip_r(n) * math.cos(angle)
            y = cy + pip_r(n) * math.sin(angle)
            pts.append((x, y, random.uniform(-wobble, wobble)))
        return pts

    # Fill shells greedily from largest (6) downward until we hit value
    # Shell sizes in order: 6, 5, 4, 3, 2, 1
    # Each shell rotated 30° more than previous
    # Explicit shell decompositions for each value
    # Fill from outside in, each shell capped at decreasing max
    # 13 = 8+4+1, 12 = 8+4, 11 = 8+3, 10 = 8+2, 9 = 8+1, 1-8 = single shell
    shell_caps = [8, 4, 1]   # max per shell, outermost first
    remaining = value
    result = []
    rotation = 0
    for cap in shell_caps:
        if remaining <= 0:
            break
        take = min(cap, remaining)
        result += make_shell(take, rotation_offset=rotation)
        remaining -= take
        rotation += 45

    return result

# --- Draw pip ---
def draw_pip(img, x, y, suit, font_pip, rotation=0):
    if suit["is_triangle"]:
        draw_triangle_symbol(img, int(x), int(y), size=36)
    else:
        sym = suit["symbol"]
        tmp = Image.new("RGB", (120, 120), BG_COLOR)
        ImageDraw.Draw(tmp).text((20, 20), sym, fill=suit["color"], font=font_pip)
        bbox = tmp.getbbox()
        if bbox:
            tmp = tmp.crop(bbox)
        if rotation != 0:
            tmp = tmp.rotate(rotation, expand=True, fillcolor=BG_COLOR)
        tw, th = tmp.size
        mask = tmp.convert("L").point(lambda p: 0 if p >= 250 else 255)
        img.paste(tmp, (int(x) - tw // 2, int(y) - th // 2), mask=mask)

# --- Draw center ---
def draw_center(img, suit, value, font_pip):
    cx, cy = WIDTH // 2, HEIGHT // 2
    r_hex = min(WIDTH, HEIGHT) // 2 - BORDER_WIDTH * 2
    for (x, y, rot) in sacred_pip_positions(value, cx, cy, r_hex):
        draw_pip(img, x, y, suit, font_pip, rotation=rot)

# --- Main ---
def generate_deck():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    suits, ranks, specials = parse_rules()
    font_large, font_pip, font_special = load_fonts()
    total = 0

    for suit in suits:
        for value, label in ranks:
            img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
            if suit["is_triangle"]:
                make_triangle_border(img)
            else:
                make_border(img, suit["color"])
            draw_center(img, suit, value, font_pip)
            mask_hex(img)
            filename = f"{OUTPUT_DIR}/{suit['label']}_{label}.jpg"
            img.save(filename, "JPEG", quality=95, dpi=(300, 300))
            print(f"  {filename}")
            total += 1

    for special in specials:
        for i in range(1, special["count"] + 1):
            img  = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
            draw = ImageDraw.Draw(img)
            color = (80, 80, 80)
            make_border(img, color)
            tw = draw.textlength(special["name"], font=font_special)
            draw.text(((WIDTH - tw) // 2, HEIGHT // 2 - 50),
                      special["name"], fill=color, font=font_special)
            mask_hex(img)
            filename = f"{OUTPUT_DIR}/{special['name']}_{i}.jpg"
            img.save(filename, "JPEG", quality=95, dpi=(300, 300))
            print(f"  {filename}")
            total += 1

    num_suits    = len(suits)
    num_ranks    = len(ranks)
    num_specials = sum(s["count"] for s in specials)
    print(f"\nDone. {total} cards saved to ./{OUTPUT_DIR}/")
    print(f"  ({num_suits} suits × {num_ranks} ranks = {num_suits * num_ranks}) + {num_specials} specials = {total}")

if __name__ == "__main__":
    generate_deck()