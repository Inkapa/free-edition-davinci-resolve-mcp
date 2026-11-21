import importlib.util
import os
import unittest

try:
    import numpy  # noqa: F401
    from PIL import Image, ImageDraw
except ImportError:  # the Linux watcher's own dependencies
    Image = None

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "autostart_bridge.py")


@unittest.skipIf(Image is None, "needs Pillow and numpy")
class WorkspacePointTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("autostart_bridge", SCRIPT)
        self.watcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.watcher)

    def test_finds_the_title_before_help(self):
        # a dark window whose menu bar holds 14 titles as light blocks; "DaVinci Resolve" is two
        # words with a narrow space, the others are one word each, Workspace is 13th
        image = Image.new("RGB", (900, 300), (24, 24, 26))
        draw = ImageDraw.Draw(image)
        x, spans = 8, []
        for words in [2] + [1] * 13:
            start = x
            for _ in range(words):
                draw.rectangle([x, 6, x + 30, 16], fill=(143, 143, 143))
                x += 30 + 4
            spans.append((start, x - 4))
            x += 14
        draw.rectangle([0, 40, 900, 60], fill=(60, 60, 64))  # toolbar below the menu bar
        left, right = spans[12]
        self.assertEqual(self.watcher.workspace_point(image), ((left + right) // 2, 11))


if __name__ == "__main__":
    unittest.main()
