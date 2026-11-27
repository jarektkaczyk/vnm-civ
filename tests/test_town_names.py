import unittest

from pipeline.build import cities


class SpellTest(unittest.TestCase):
    PLACES = [
        {"name": "Trảng Bàng", "place": "town", "lon": 106.37, "lat": 11.03},
        {"name": "Thị trấn Vạn Giã", "place": "town", "lon": 109.2, "lat": 12.7},
        {"name": "Trảng Bàng", "place": "village", "lon": 100.0, "lat": 5.0},
    ]

    def test_plain_name_takes_the_tone_marks_of_the_nearest_place(self):
        self.assertEqual(cities.spell("Trang Bang", 106.4, 11.0, self.PLACES), "Trảng Bàng")

    def test_english_suffix_is_dropped_and_the_prefix_too(self):
        self.assertEqual(cities.spell("Van Gia Town", 109.2, 12.7, self.PLACES), "Vạn Giã")

    def test_name_without_a_match_stays_plain(self):
        self.assertEqual(cities.spell("Pleiku", 108.0, 13.9, self.PLACES), "Pleiku")
        self.assertEqual(cities.spell("Trang Bang", 110.0, 20.0, self.PLACES), "Trang Bang")

    def test_official_spelling_of_a_provincial_centre_is_the_fallback(self):
        known = {"ninhbinh": "Ninh B\u00ecnh"}
        self.assertEqual(cities.spell("Ninh Binh", 106.0, 20.1, self.PLACES, known), "Ninh B\u00ecnh")

    def test_name_with_marks_is_kept(self):
        self.assertEqual(cities.spell("Cần Thơ", 105.7, 10.0, self.PLACES), "Cần Thơ")


if __name__ == "__main__":
    unittest.main()
