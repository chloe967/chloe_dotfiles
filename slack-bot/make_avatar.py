#!/usr/bin/env python3
"""Generate Rocky the PM's avatar (a mountain with a summit flag).

Regenerable so the asset has a single source of truth. Run:
    python make_avatar.py            # writes rocky_avatar.png (512x512)
Then upload the PNG in the Slack app config -> Basic Information ->
Display Information -> app icon.
"""
from PIL import Image, ImageDraw

SIZE = 512
img = Image.new("RGB", (SIZE, SIZE), "#FFD6A5")
d = ImageDraw.Draw(img)

# Warm sunrise sky: vertical gradient top -> bottom.
top, bot = (255, 214, 165), (255, 158, 122)
for y in range(SIZE):
    t = y / SIZE
    d.line([(0, y), (SIZE, y)],
           fill=tuple(round(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

# Sun.
d.ellipse([90, 90, 210, 210], fill="#FFF1C1")

# Back ridges (muted, sit on the baseline).
d.polygon([(30, 512), (200, 250), (360, 512)], fill="#8391AE")
d.polygon([(300, 512), (430, 300), (560, 512)], fill="#8391AE")

# Front peak.
PEAK = (280, 165)
d.polygon([(55, 512), PEAK, (505, 512)], fill="#46516B")
# Snow cap.
d.polygon([PEAK, (240, 250), (262, 238), (282, 252), (300, 236), (322, 250)],
          fill="#FFFFFF")

# Summit flag (a PM planting the flag on the milestone).
d.line([PEAK, (280, 108)], fill="#2B2B2B", width=7)
d.polygon([(280, 110), (338, 126), (280, 150)], fill="#E4572E")

img.save("/home/ubuntu/git/chloe_dotfiles/slack-bot/rocky_avatar.png")
print("wrote rocky_avatar.png")
