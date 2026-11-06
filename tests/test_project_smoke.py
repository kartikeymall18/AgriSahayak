import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PackageSmokeTests(unittest.TestCase):
    def test_python_sources_parse(self):
        files = [p for p in ROOT.rglob("*.py")
                 if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)]
        self.assertGreaterEqual(len(files), 20)
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    def test_config_has_no_embedded_provider_keys(self):
        text = (ROOT / "config.py").read_text(encoding="utf-8-sig")
        self.assertRegex(text, r'(?m)^XAI_API_KEY\s*=\s*["\']{2}')
        self.assertRegex(text, r'(?m)^GROQ_API_KEY\s*=\s*["\']{2}')
        self.assertNotRegex(text, r"(?i)(gsk_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9_-]{20,}|hf_[A-Za-z0-9]{20,})")

    def test_localhost_is_the_default_bind_address(self):
        config = (ROOT / "config.py").read_text(encoding="utf-8-sig")
        self.assertIn('HOST = "127.0.0.1"', config)

    def test_support_detects_crop_alias_and_loss_route(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import support
        self.assertEqual(support.detect_crop("आलू"), "potato")
        result = support.recommend(issue="crop loss and insurance claim")
        self.assertEqual(result["recommendations"][0]["id"], "pmfby")
        self.assertIn("confirm", result["notice"].lower())

    def test_horticulture_scheme_is_a_referral_not_an_eligibility_result(self):
        import sys
        sys.path.insert(0, str(ROOT))
        import support
        result = support.recommend(crop="tomato", issue="government scheme")
        ids = {item["id"] for item in result["recommendations"]}
        self.assertIn("midh", ids)
        self.assertTrue(result["location_needed"])
        self.assertIn("does not submit applications", result["notice"])

    def test_tablet_ui_exposes_camera_fullscreen_and_reply_language(self):
        html = (ROOT / "static" / "tablet.html").read_text(encoding="utf-8")
        for marker in ('id="btnFullscreen"', 'id="btnPhoto"', 'id="btnAuto"', 'id="talkLang"', 'id="btnUsb"'):
            with self.subTest(marker=marker):
                self.assertIn(marker, html)

    def test_public_copy_omits_runtime_data_and_weight_artifacts(self):
        forbidden = {"records.jsonl", "settings.json", "model.safetensors", "tokenizer.json"}
        for path in ROOT.rglob("*"):
            if path.is_file():
                self.assertNotIn(path.name, forbidden, str(path.relative_to(ROOT)))
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".env", "data/", "voice_models/", "__pycache__/", "*.safetensors"):
            with self.subTest(pattern=pattern):
                self.assertIn(pattern, ignore)
        self.assertTrue((ROOT / "scripts" / "privacy_audit.py").is_file())


if __name__ == "__main__":
    unittest.main()

