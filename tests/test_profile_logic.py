#!/usr/bin/env python3
"""profile_logic 純函數的單元測試（不需 applaud / 真 API）。

執行：python3 tests/test_profile_logic.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import profile_logic  # noqa: E402


def _profile(name):
    return {"id": name, "attributes": {"name": name}}


class FilterProfilesByExactNameTest(unittest.TestCase):
    """根因迴歸測試：Apple filter[name] 是前綴/包含比對，
    必須只保留 name 完全相符者，否則 EcogeniePlus 會誤刪別人的 profile。"""

    def test_keeps_only_exact_name_match(self):
        # 重現 EcogeniePlus 情境：查 "AppStore io.nextdrive.ecogenie"
        # Apple 回傳含一堆 .xxx 前綴 match。
        api_profiles = [
            _profile("AppStore io.nextdrive.ecogenie"),
            _profile("AppStore io.nextdrive.ecogenie.rco"),
            _profile("AppStore io.nextdrive.ecogenie.stgreen"),
            _profile("AppStore io.nextdrive.ecogenie.ecube"),
        ]
        result = profile_logic.filter_profiles_by_exact_name(
            api_profiles, "AppStore io.nextdrive.ecogenie"
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["attributes"]["name"], "AppStore io.nextdrive.ecogenie")

    def test_keeps_genuine_duplicates(self):
        # 真正同名重複（Apple 偶有重複 profile）要全部保留。
        api_profiles = [
            _profile("AppStore io.nextdrive.ecogenie.rco"),
            _profile("AppStore io.nextdrive.ecogenie.rco"),
            _profile("AppStore io.nextdrive.ecogenie"),
        ]
        result = profile_logic.filter_profiles_by_exact_name(
            api_profiles, "AppStore io.nextdrive.ecogenie.rco"
        )
        self.assertEqual(len(result), 2)

    def test_no_match_returns_empty(self):
        result = profile_logic.filter_profiles_by_exact_name(
            [_profile("AppStore io.nextdrive.ecogenie.rco")], "AppStore io.nextdrive.ecogenie"
        )
        self.assertEqual(result, [])

    def test_handles_missing_attributes_gracefully(self):
        api_profiles = [{"id": "x"}, _profile("AppStore foo")]
        result = profile_logic.filter_profiles_by_exact_name(api_profiles, "AppStore foo")
        self.assertEqual(len(result), 1)


class EvaluateProfileVerificationTest(unittest.TestCase):
    """self-verification 判斷：建立後重查 Apple，必須 ACTIVE + 正確 bundle + 含正確 cert。"""

    def _detail(self, state="ACTIVE", bundle_id="BUNDLE1", cert_ids=("CERT1",)):
        return {
            "data": {
                "attributes": {"profileState": state},
                "relationships": {
                    "bundleId": {"data": {"id": bundle_id}},
                    "certificates": {"data": [{"id": c} for c in cert_ids]},
                },
            }
        }

    def test_all_correct_passes(self):
        ok, reason = profile_logic.evaluate_profile_verification(
            self._detail(), "BUNDLE1", "CERT1"
        )
        self.assertTrue(ok, reason)
        self.assertEqual(reason, "")

    def test_inactive_state_fails(self):
        ok, reason = profile_logic.evaluate_profile_verification(
            self._detail(state="INVALID"), "BUNDLE1", "CERT1"
        )
        self.assertFalse(ok)
        self.assertIn("INVALID", reason)

    def test_wrong_bundle_fails(self):
        ok, reason = profile_logic.evaluate_profile_verification(
            self._detail(bundle_id="OTHER"), "BUNDLE1", "CERT1"
        )
        self.assertFalse(ok)
        self.assertIn("bundle", reason.lower())

    def test_missing_cert_fails(self):
        ok, reason = profile_logic.evaluate_profile_verification(
            self._detail(cert_ids=("CERT_OTHER",)), "BUNDLE1", "CERT1"
        )
        self.assertFalse(ok)
        self.assertIn("cert", reason.lower())

    def test_cert_among_several_passes(self):
        ok, reason = profile_logic.evaluate_profile_verification(
            self._detail(cert_ids=("CERT_OTHER", "CERT1")), "BUNDLE1", "CERT1"
        )
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
