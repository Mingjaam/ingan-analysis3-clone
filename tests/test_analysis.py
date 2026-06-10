import unittest

from app import analyze_dataset, app


class AnalysisTest(unittest.TestCase):
    def test_analyze_dataset_returns_report_shape(self):
        dataset = {
            "profile": {
                "id": "1",
                "username": "sample",
                "account_type": "BUSINESS",
                "followers_count": 1200,
                "media_count": 2,
            },
            "media": [
                {
                    "id": "m1",
                    "caption": "오늘은 혼자 있지만 마음은 고마워요",
                    "media_type": "IMAGE",
                    "like_count": 20,
                    "comments_count": 2,
                    "comments": [
                        {"username": "friend_a", "text": "너무 좋아 보여"},
                        {"username": "friend_b", "text": "괜찮아?"},
                    ],
                },
                {
                    "id": "m2",
                    "caption": "우리 다시 함께 걷자",
                    "media_type": "VIDEO",
                    "like_count": 35,
                    "comments_count": 1,
                    "comments": [{"username": "friend_a", "text": "사랑스럽다"}],
                },
            ],
        }
        result = analyze_dataset(dataset, {"handle": "sample", "question": "나를 무장해제 시키는 칭찬 세가지는?"})
        self.assertIn("archetype", result)
        self.assertIn("scores", result)
        self.assertEqual(result["profile"]["username"], "sample")
        self.assertEqual(result["evidence"]["mediaAnalyzed"], 2)
        self.assertEqual(result["evidence"]["commentsAnalyzed"], 3)
        self.assertGreaterEqual(len(result["chapters"]), 4)

    def test_unconfigured_start_returns_setup_required(self):
        client = app.test_client()
        response = client.post("/api/analysis/start", json={"handle": "sample"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "setup_required")


if __name__ == "__main__":
    unittest.main()
