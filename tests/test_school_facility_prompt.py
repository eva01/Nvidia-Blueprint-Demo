import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = ROOT / "config" / "prompt.yaml"


class SchoolFacilityPromptTests(unittest.TestCase):
    def test_prompt_reprompts_for_invalid_fixed_choice_answers(self) -> None:
        prompt = yaml.safe_load(PROMPT_FILE.read_text(encoding="utf-8"))
        content = prompt["nemotron-3-nano"]["school_facility_support"]["messages"][0]["content"]

        self.assertIn("Validate fixed-choice answers before storing them", content)
        self.assertIn(
            "If a category answer is not one of the allowed categories, say it is not a valid category",
            content,
        )
        self.assertIn("If an urgency answer is not low, normal, or urgent, say it is not a valid urgency", content)
        self.assertIn("For yes or no safety questions, accept only yes or no", content)
        self.assertIn("Do not treat invalid fixed-choice answers as other fields", content)


if __name__ == "__main__":
    unittest.main()
