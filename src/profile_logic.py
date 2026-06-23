"""純邏輯函數（不依賴 applaud / requests），供 main.py 引用並可單元測試。"""
from typing import Any, Dict, List, Tuple


def filter_profiles_by_exact_name(
    api_profiles: List[Dict[str, Any]], profile_name: str
) -> List[Dict[str, Any]]:
    """只保留 name 與 profile_name 完全相符的 profile。

    Apple 的 filter[name] 是前綴/包含比對，會把例如
    "AppStore io.nextdrive.ecogenie.rco" 也當成
    "AppStore io.nextdrive.ecogenie" 的結果回傳；若不在此精確過濾，
    名稱為其他 profile 前綴者（如 EcogeniePlus）會誤刪一大批別人的 profile。
    """
    return [
        p
        for p in api_profiles
        if (p.get("attributes") or {}).get("name") == profile_name
    ]


def evaluate_profile_verification(
    profile_detail: Dict[str, Any], expected_bundle_id: str, expected_cert_id: str
) -> Tuple[bool, str]:
    """檢查（建立後重查的）profile 詳情是否完全正確。

    Args:
        profile_detail: GET /v1/profiles/{id}?include=bundleId,certificates 的 JSON
        expected_bundle_id: 預期綁定的 Apple bundleId object id
        expected_cert_id: 預期綁定的 certificate id

    Returns:
        (ok, reason)：ok 為 True 表示 ACTIVE 且 bundle/cert 皆正確；
        否則 ok 為 False，reason 說明哪一項不符。
    """
    data = profile_detail.get("data") or {}
    attrs = data.get("attributes") or {}

    state = attrs.get("profileState", "UNKNOWN")
    if state != "ACTIVE":
        return False, f"profileState={state}（預期 ACTIVE）"

    rels = data.get("relationships") or {}

    actual_bundle = ((rels.get("bundleId") or {}).get("data") or {}).get("id")
    if actual_bundle != expected_bundle_id:
        return False, f"bundleId={actual_bundle}（預期 {expected_bundle_id}）"

    cert_ids = [
        c.get("id") for c in ((rels.get("certificates") or {}).get("data") or [])
    ]
    if expected_cert_id not in cert_ids:
        return False, f"certificates={cert_ids}（預期含 {expected_cert_id}）"

    return True, ""
