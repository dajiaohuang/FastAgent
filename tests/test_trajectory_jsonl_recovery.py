import json
import tempfile
import unittest
from pathlib import Path

from fastagent.recording.utils import load_trajectory_from_jsonl


class TrajectoryJsonlRecoveryTests(unittest.TestCase):
    def test_truncated_tail_preserves_complete_records(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp_dir:
            trajectory_path = Path(temp_dir) / "traj.jsonl"
            complete_record = {"step": 1, "tool": "synthetic"}
            trajectory_path.write_text(
                json.dumps(complete_record) + "\n" + '{"step": 2',
                encoding="utf-8",
            )

            self.assertEqual(
                load_trajectory_from_jsonl(str(trajectory_path)), [complete_record]
            )


if __name__ == "__main__":
    unittest.main()
