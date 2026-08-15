from __future__ import annotations

import unittest

from aletheion_black_box.evidence import redact


class RedactionTests(unittest.TestCase):
    def test_redacts_secret_fields_and_values_recursively(self) -> None:
        value = {
            "Authorization": "Bearer secret-value",
            "nested": {"api_key": "secret-value", "message": "prefix secret-value suffix"},
        }
        self.assertEqual(
            redact(value, ("secret-value",)),
            {
                "Authorization": "[REDACTED]",
                "nested": {"api_key": "[REDACTED]", "message": "prefix [REDACTED] suffix"},
            },
        )


if __name__ == "__main__":
    unittest.main()
