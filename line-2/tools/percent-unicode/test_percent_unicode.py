import unittest

from percent_unicode import scan


class PercentUnicodeTests(unittest.TestCase):
    def test_reports_exact_utf8_escape_and_coordinates(self):
        result = scan(b"x\nq=%D1%96")
        self.assertEqual(result["findings"], 1)
        item = result["details"][0]
        self.assertEqual(item["codepoint"], "U+0456")
        self.assertEqual(item["source_byte_range"], [4, 10])
        self.assertEqual((item["source_line"], item["source_byte_column"]), (2, 3))

    def test_ascii_escapes_are_not_unicode(self):
        self.assertEqual(scan(b"%6F%77ner")["findings"], 0)

    def test_malformed_or_invalid_utf8_is_ignored(self):
        self.assertEqual(scan(b"%GG %C0%AF %ED%A0%80 %F4%90%80%80")["findings"], 0)

    def test_cap_preserves_total(self):
        result = scan(b"%C3%A9 %E2%80%AE", max_findings=1)
        self.assertEqual((result["findings"], result["retained_details"], result["omitted_details"]), (2, 1, 1))

    def test_literal_utf8_is_out_of_scope(self):
        self.assertEqual(scan("é".encode())["findings"], 0)


if __name__ == "__main__":
    unittest.main()
