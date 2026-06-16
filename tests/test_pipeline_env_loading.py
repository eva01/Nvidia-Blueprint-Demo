import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "src" / "pipeline.py"


class PipelineEnvLoadingTests(unittest.TestCase):
    def test_pipeline_does_not_override_explicit_shell_environment_with_dotenv(self) -> None:
        pipeline_source = PIPELINE.read_text(encoding="utf-8")

        self.assertIn("load_dotenv(override=False)", pipeline_source)
        self.assertNotIn("load_dotenv(override=True)", pipeline_source)

    def test_webrtc_pipeline_exposes_asr_endpointing_wait_controls(self) -> None:
        pipeline_source = PIPELINE.read_text(encoding="utf-8")

        self.assertIn("def _env_int(", pipeline_source)
        self.assertIn('"ASR_STOP_HISTORY"', pipeline_source)
        self.assertIn('"ASR_STOP_HISTORY_EOU"', pipeline_source)
        self.assertIn('"stop_history": _env_int("ASR_STOP_HISTORY", 500)', pipeline_source)
        self.assertIn('"stop_history_eou": _env_int("ASR_STOP_HISTORY_EOU", 240)', pipeline_source)

    def test_websocket_pipeline_exposes_asr_endpointing_wait_controls(self) -> None:
        websocket_source = (ROOT / "src" / "pipeline_websocket.py").read_text(encoding="utf-8")

        self.assertIn("def _env_int(", websocket_source)
        self.assertIn('"ASR_STOP_HISTORY"', websocket_source)
        self.assertIn('"ASR_STOP_HISTORY_EOU"', websocket_source)
        self.assertIn('"stop_history": _env_int("ASR_STOP_HISTORY", 500)', websocket_source)
        self.assertIn('"stop_history_eou": _env_int("ASR_STOP_HISTORY_EOU", 240)', websocket_source)

    def test_cloud_example_prefers_deliberate_turn_taking_for_demo(self) -> None:
        env_cloud = (ROOT / "config" / "env.cloud.example").read_text(encoding="utf-8")

        self.assertIn("ENABLE_SPECULATIVE_SPEECH=false", env_cloud)
        self.assertIn("ASR_STOP_HISTORY=900", env_cloud)
        self.assertIn("ASR_STOP_HISTORY_EOU=900", env_cloud)


if __name__ == "__main__":
    unittest.main()
