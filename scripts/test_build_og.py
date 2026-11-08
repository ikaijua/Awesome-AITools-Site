import tempfile
import unittest
from pathlib import Path

import build_og


class TestBuildOg(unittest.TestCase):
    def test_font_resolves(self):
        self.assertIsNotNone(build_og.font(24, True))

    def test_wraps_without_breaking_ascii_words(self):
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (10, 10))
        draw = ImageDraw.Draw(img)
        face = build_og.font(30)
        lines = build_og.wrap(draw, "GPT-6.1 Sol 与 GPT-6 Luna 将 API 价格下调约 50%", face, 480, 3)
        self.assertTrue(lines)
        for line in lines[:-1]:
            # no line may end in the middle of a latin word+space join artifact
            self.assertFalse(line.endswith("GP"))

    def test_build_creates_cards_for_tool_and_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_og.build(Path(tmp), "https://example.com/", only="chatgpt")
            self.assertGreaterEqual(result["cards"], 1)
            made = list(Path(tmp).rglob("*.png"))
            self.assertTrue(made)
            for png in made:
                self.assertGreater(png.stat().st_size, 10_000)


if __name__ == "__main__":
    unittest.main()
