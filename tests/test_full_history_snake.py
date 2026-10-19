import sys
import unittest
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_full_history_snake import animation, render


class SnakeTests(unittest.TestCase):
    def setUp(self):
        self.history = {
            2025: {
                date(2025, 2, 11): (2, 3),
                date(2025, 11, 5): (4, 7),
            },
            2026: {
                date(2026, 2, 11): (1, 1),
                date(2026, 10, 19): (3, 5),
            },
        }

    def test_renders_all_years_and_all_known_days(self):
        svg = render("LuizHvD", self.history, date(2026, 10, 19), "light")
        ET.fromstring(svg)
        self.assertIn("2025–2026", svg)
        self.assertIn("2025-02-11: 3 contribuições", svg)
        self.assertIn("2025-11-05: 7 contribuições", svg)
        self.assertIn("2026-10-19: 5 contribuições", svg)
        self.assertIn("2025", svg)
        self.assertIn("2026", svg)
        self.assertIn("@keyframes travel-2025", svg)
        self.assertIn("@keyframes travel-2026", svg)

    def test_dark_theme(self):
        svg = render("LuizHvD", self.history, date(2026, 10, 19), "dark")
        ET.fromstring(svg)
        self.assertIn('#0b1423', svg)
        self.assertIn('prefers-reduced-motion', svg)

    def test_animates_single_contribution(self):
        css, shape = animation(2025, [(100.0, 20.0)])
        self.assertIn("100%", css)
        self.assertIn("travel-2025", css)
        self.assertIn('circle', shape)


if __name__ == "__main__":
    unittest.main()
