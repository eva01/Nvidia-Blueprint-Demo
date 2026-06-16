import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_cloud_nim_config import (
    filter_active_functions,
    load_env_file,
    mask_secret,
    validate_cloud_nim_config,
)


class CloudNimConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.prompt_file = self.root / "prompt.yaml"
        self.prompt_file.write_text(
            """
nemotron-3-nano:
  school_facility_support:
    messages:
      - role: user
        content: School facilities support.
""",
            encoding="utf-8",
        )
        self.db_path = self.root / "data" / "facility_tickets.db"
        self.base_env = {
            "NVIDIA_API_KEY": "nvapi-test-secret-value",
            "TRANSPORT": "WEBRTC",
            "SYSTEM_PROMPT_SELECTOR": "nemotron-3-nano/school_facility_support",
            "PROMPT_FILE_PATH": str(self.prompt_file),
            "ASR_SERVER_URL": "grpc.nvcf.nvidia.com:443",
            "TTS_SERVER_URL": "grpc.nvcf.nvidia.com:443",
            "NVIDIA_LLM_URL": "https://integrate.api.nvidia.com/v1",
            "FACILITY_TICKETS_DB_PATH": str(self.db_path),
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_validate_cloud_nim_config_accepts_expected_cloud_settings(self) -> None:
        result = validate_cloud_nim_config(self.base_env, repo_root=self.root)

        self.assertEqual(result.errors, [])
        self.assertTrue(result.db_parent_created)
        self.assertTrue(self.db_path.parent.exists())
        output = "\n".join(result.checks)
        self.assertIn("prompt selector", output)
        self.assertIn("SOVEREIGN_MODE is local-demo", output)
        self.assertIn("PII_REDACTION_ENABLED is false", output)
        self.assertIn("AUDIT_LOG_ENABLED is true", output)

    def test_validate_cloud_nim_config_rejects_missing_key_without_leaking_values(self) -> None:
        env = dict(self.base_env)
        env.pop("NVIDIA_API_KEY")

        result = validate_cloud_nim_config(env, repo_root=self.root)

        self.assertTrue(result.errors)
        output = "\n".join(result.errors + result.checks)
        self.assertIn("NVIDIA_API_KEY is required", output)
        self.assertNotIn("nvapi-test-secret-value", output)

    def test_validate_cloud_nim_config_rejects_local_endpoints_and_wrong_prompt(self) -> None:
        env = dict(self.base_env)
        env.update(
            {
                "SYSTEM_PROMPT_SELECTOR": "nemotron-3-nano/generic_voice_assistant",
                "ASR_SERVER_URL": "asr-service:50052",
                "TTS_SERVER_URL": "tts-service:50051",
                "NVIDIA_LLM_URL": "http://nvidia-llm:8000/v1",
            }
        )

        result = validate_cloud_nim_config(env, repo_root=self.root)

        output = "\n".join(result.errors)
        self.assertIn("SYSTEM_PROMPT_SELECTOR", output)
        self.assertIn("ASR_SERVER_URL", output)
        self.assertIn("TTS_SERVER_URL", output)
        self.assertIn("NVIDIA_LLM_URL", output)

    def test_validate_cloud_nim_config_requires_explicit_cloud_nim_allowance(self) -> None:
        env = dict(self.base_env)
        env["ALLOW_CLOUD_NIM"] = "false"

        result = validate_cloud_nim_config(env, repo_root=self.root)

        self.assertIn("ALLOW_CLOUD_NIM must be true", "\n".join(result.errors))

    def test_load_env_file_parses_values_without_overriding_explicit_environment(self) -> None:
        env_file = self.root / ".env"
        env_file.write_text(
            """
# comment
TRANSPORT=WEBSOCKET
NVIDIA_API_KEY=from-file
SYSTEM_PROMPT_SELECTOR=nemotron-3-nano/school_facility_support
""",
            encoding="utf-8",
        )

        loaded = load_env_file(env_file, environ={"NVIDIA_API_KEY": "from-shell"})

        self.assertEqual(loaded["TRANSPORT"], "WEBSOCKET")
        self.assertEqual(loaded["NVIDIA_API_KEY"], "from-shell")

    def test_mask_secret_never_returns_full_secret(self) -> None:
        self.assertEqual(mask_secret(""), "<unset>")
        self.assertEqual(mask_secret("short"), "<set>")
        self.assertEqual(mask_secret("nvapi-test-secret-value"), "nvapi...alue")

    def test_filter_active_functions_returns_matching_active_names(self) -> None:
        payload = {
            "functions": [
                {"id": "inactive", "name": "ai-parakeet-ctc-1_1b-asr", "status": "INACTIVE"},
                {"id": "asr-id", "name": "ai-parakeet-ctc-1_1b-asr", "status": "ACTIVE"},
                {"id": "tts-id", "name": "ai-magpie-tts-multilingual", "status": "ACTIVE"},
                {"id": "llm-id", "name": "ai-something-else", "status": "ACTIVE"},
            ]
        }

        matches = filter_active_functions(payload, ["parakeet", "magpie"])

        self.assertEqual(matches, [("asr-id", "ai-parakeet-ctc-1_1b-asr"), ("tts-id", "ai-magpie-tts-multilingual")])

    def test_direct_script_execution_can_import_local_modules(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / "check_cloud_nim_config.py"), "--help"],
            cwd=self.root,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Validate cloud NIM school facility demo settings", result.stdout)


if __name__ == "__main__":
    unittest.main()
