"""Calm dark wallpaper made to sit behind the glass dashboard — run: python3 ~/.stark/wallpaper_glass.py"""
import os, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

W, H = 2940, 1912
img = Image.new("RGB", (W, H), (9, 8, 8))
glow = Image.new("RGB", (W, H), (0, 0, 0)); g = ImageDraw.Draw(glow)
for (cx, cy, r, col) in [
    (420, 260, 900, (120, 62, 18)),     # warm amber bloom, top-left
    (1500, 980, 1100, (34, 22, 14)),    # faint warm centre
    (2620, 1700, 950, (14, 40, 64)),    # cool arc-blue bloom, bottom-right
]:
    g.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
glow = glow.filter(ImageFilter.GaussianBlur(320))
img = ImageChops.add(img, glow)

# a soft diagonal light streak
streak = Image.new("L", (W, H), 0); ImageDraw.Draw(streak).polygon([(900, 0), (1250, 0), (450, H), (100, H)], fill=26)
streak = streak.filter(ImageFilter.GaussianBlur(160))
img = Image.composite(Image.new("RGB", (W, H), (255, 214, 160)), img, streak)

# fine film grain
random.seed(3)
noise = Image.effect_noise((W, H), 18).convert("L").point(lambda v: 128 + (v - 128) // 6)
img = ImageChops.overlay(img, Image.merge("RGB", [noise] * 3))

# vignette
vig = Image.new("L", (W, H), 0); ImageDraw.Draw(vig).ellipse([-W * .15, -H * .2, W * 1.15, H * 1.2], fill=255)
vig = vig.filter(ImageFilter.GaussianBlur(260))
img = Image.composite(img, Image.new("RGB", (W, H), (3, 3, 3)), vig)

out = os.path.expanduser("~/Pictures/Wallpapers/Midnight-Glass.png")
img.save(out); print(out)
