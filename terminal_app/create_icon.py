from PIL import Image, ImageDraw
import math

def create_soccer_ball_icon(path="icon.ico"):
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy, r = 128, 128, 116

    # Draw soft outer glow / shadow
    for i in range(8):
        draw.ellipse([cx - r - i, cy - r - i, cx + r + i, cy + r + i], outline=(20, 100, 40, 15 - i * 2), width=2)

    # Ball background (vibrant gradient green circle rim + white ball)
    draw.ellipse([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4], fill=(24, 140, 60, 255))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 248, 250, 255), outline=(40, 40, 40, 255), width=6)

    # Center black pentagon
    pentagon_r = 38
    angles = [i * 72 - 90 for i in range(5)]
    points = [(cx + pentagon_r * math.cos(math.radians(a)), cy + pentagon_r * math.sin(math.radians(a))) for a in angles]
    draw.polygon(points, fill=(28, 32, 38, 255))

    # Outer black patches connecting to the center pentagon
    for i in range(5):
        p1 = points[i]
        p2 = points[(i + 1) % 5]

        # calculate outer radiating points
        mid_angle = (angles[i] + angles[(i + 1) % 5]) / 2
        # outward point
        outer_r1 = 80
        out_pt1 = (cx + outer_r1 * math.cos(math.radians(angles[i])), cy + outer_r1 * math.sin(math.radians(angles[i])))
        draw.line([p1, out_pt1], fill=(45, 50, 55, 255), width=5)

        edge_r = r - 2
        edge_pt = (cx + edge_r * math.cos(math.radians(mid_angle)), cy + edge_r * math.sin(math.radians(mid_angle)))
        corner1 = (cx + edge_r * math.cos(math.radians(mid_angle - 22)), cy + edge_r * math.sin(math.radians(mid_angle - 22)))
        corner2 = (cx + edge_r * math.cos(math.radians(mid_angle + 22)), cy + edge_r * math.sin(math.radians(mid_angle + 22)))
        draw.polygon([out_pt1, corner1, corner2], fill=(30, 35, 42, 255))

    # Highlights
    draw.arc([cx - r + 8, cy - r + 8, cx + r - 8, cy + r - 8], start=200, end=290, fill=(255, 255, 255, 180), width=8)

    # Save as multi-resolution Windows ICO
    img.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icon created successfully at {path}")

if __name__ == "__main__":
    create_soccer_ball_icon()
