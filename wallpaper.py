"""Bat-signal x arc reactor x AI wallpaper generator — run: python3 ~/.stark/wallpaper.py"""
import math, random
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 2560, 1664
random.seed(7)
img = Image.new("RGB", (W, H))
px = img.load()
# Background: Gotham midnight-blue (left) -> Stark deep crimson (right)
for x in range(W):
    t = x / W
    for y in range(H):
        v = 1 - 0.55 * (y / H)
        r = int((6 + 38 * t**2) * v); g = int((10 + 2 * t) * v); b = int((22 - 12 * t) * v)
        px[x, y] = (r, g, b)

glow = Image.new("RGB", (W, H)); gd = ImageDraw.Draw(glow)
lines = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lines)

# --- AI neural network mesh across the middle ---
nodes = [(random.randint(500, 2060), random.randint(250, 1350)) for _ in range(70)]
for i, a in enumerate(nodes):
    for b in nodes[i + 1:]:
        d = math.dist(a, b)
        if d < 230:
            t = a[0] / W
            col = (int(80 + 160 * t), int(200 - 60 * t), int(255 - 180 * t), int(90 * (1 - d / 230)))
            ld.line([a, b], fill=col, width=2)
for (x, y) in nodes:
    t = x / W
    ld.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(int(120 + 130 * t), 220, int(255 - 120 * t), 200))

# --- Circuit traces ---
for _ in range(40):
    x, y = random.randint(0, W), random.randint(0, H)
    pts = [(x, y)]
    for _ in range(4):
        if random.random() < .5: x += random.choice([-1, 1]) * random.randint(60, 220)
        else: y += random.choice([-1, 1]) * random.randint(60, 220)
        pts.append((x, y))
    ld.line(pts, fill=(0, 200, 255, 35), width=2)
    ld.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(0, 200, 255, 60), width=2)

# --- Batman: bat-signal moon + bat silhouette (left) ---
cx, cy, R = 620, 640, 330
gd.ellipse([cx - R - 60, cy - R - 60, cx + R + 60, cy + R + 60], fill=(70, 90, 140))
moon = Image.new("RGBA", (W, H), (0, 0, 0, 0)); md = ImageDraw.Draw(moon)
md.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(235, 205, 90, 255))
bat = [(0,-30),(18,-60),(22,-22),(60,-34),(140,-80),(250,-70),(330,-20),(300,-10),(270,15),(230,10),(200,40),(150,25),(110,55),(70,30),(30,40),(0,90)]
bat = bat + [(-x, y) for (x, y) in reversed(bat[:-1])]
s = 0.95
md.polygon([(cx + x * s, cy + y * s) for x, y in bat], fill=(5, 8, 15, 255))

# --- Iron Man: arc reactor (right) ---
ax, ay = 1940, 640
for r, a in [(380, 40), (300, 70), (230, 110)]:
    gd.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(int(a * .5), int(a * 1.6), int(a * 2.2)))
for r, w, c in [(300, 6, (200, 30, 30, 255)), (270, 3, (230, 180, 60, 255)), (240, 14, (120, 220, 255, 220)),
                (190, 4, (230, 180, 60, 255)), (110, 10, (190, 245, 255, 255))]:
    ld.ellipse([ax - r, ay - r, ax + r, ay + r], outline=c, width=w)
for i in range(10):  # coil segments
    a0 = i * 36
    ld.arc([ax - 225, ay - 225, ax + 225, ay + 225], a0 + 4, a0 + 30, fill=(220, 250, 255, 255), width=26)
tri = [(ax + 150 * math.cos(math.radians(a)), ay + 150 * math.sin(math.radians(a))) for a in (-90, 30, 150)]
ld.polygon(tri, outline=(190, 245, 255, 255), width=8)
ld.ellipse([ax - 55, ay - 55, ax + 55, ay + 55], fill=(230, 252, 255, 255))

# --- Stock ticker line across the bottom ---
pts, y = [], 1380
for x in range(0, W + 20, 20):
    y += random.gauss(-1.2, 14); y = max(1240, min(1520, y)); pts.append((x, y))
ld.line(pts, fill=(40, 255, 140, 170), width=4)
gd.line(pts, fill=(20, 160, 80), width=18)
for x in range(0, W, 160): ld.line([(x, 1220), (x, 1560)], fill=(255, 255, 255, 12))

glow = glow.filter(ImageFilter.GaussianBlur(70))
img = Image.blend(img, Image.eval(Image.merge("RGB", [a.point(lambda v: v) for a in glow.split()]), lambda v: v), 0)
from PIL import ImageChops
img = ImageChops.add(img, glow)
img.paste(moon.filter(ImageFilter.GaussianBlur(1)), (0, 0), moon)
soft = lines.filter(ImageFilter.GaussianBlur(6))
img.paste(soft, (0, 0), soft); img.paste(lines, (0, 0), lines)

# --- Labels ---
d = ImageDraw.Draw(img)
def font(sz):
    for f in ["/System/Library/Fonts/Supplemental/Futura.ttc", "/System/Library/Fonts/Helvetica.ttc"]:
        try: return ImageFont.truetype(f, sz)
        except OSError: pass
    return ImageFont.load_default()
img.save(__import__("os").path.expanduser("~/.stark/wallpaper.png"))
print("saved")
