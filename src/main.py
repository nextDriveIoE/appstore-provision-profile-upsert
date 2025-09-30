#!/usr/bin/env python3
"""
App Store Provision Profile Upsert Action
使用 Applaud 套件來更新或建立 Provisioning Profile
"""

import os
import sys
import base64
import tempfile
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from applaud.connection import Connection
    from applaud.endpoints.profiles import ProfileCreateRequest, ProfilesEndpoint
    from applaud.endpoints.certificates import CertificateType, ProfileType
    from applaud.endpoints import EndpointException
except ImportError as e:
    logger.error(f"無法導入 Applaud 套件: {e}")
    logger.error("請確保已安裝 applaud 套件: pip install applaud")
    sys.exit(1)


class ProvisioningProfileManager:
    """Provisioning Profile 管理器"""
    
    def __init__(self, issuer_id: str, key_id: str, private_key: str):
        """初始化連接"""
        self.connection = Connection(issuer_id, key_id, private_key)
        logger.info("已建立 App Store Connect API 連接")
    
    def find_available_certificate(self, cert_type: str) -> Optional[Dict[str, Any]]:
        """尋找可用的證書"""
        logger.info(f"尋找類型為 {cert_type} 的可用證書...")
        
        try:
            # 列出所有證書
            certificates = self.connection.certificates().get()
            
            valid_certs = []
            current_time = datetime.now(timezone.utc)
            
            for cert in certificates.data:
                # 過濾證書類型
                if cert.attributes.certificate_type != cert_type:
                    continue
                    
                # 檢查證書是否過期
                exp_date = cert.attributes.expiration_date
                
                # 如果 exp_date 是字串，轉換為 datetime
                if isinstance(exp_date, str):
                    exp_date = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
                
                if exp_date > current_time:
                    valid_certs.append({
                        'id': cert.id,
                        'name': cert.attributes.name,
                        'display_name': cert.attributes.display_name,
                        'expiration_date': exp_date.isoformat() if isinstance(exp_date, datetime) else exp_date,
                        'platform': cert.attributes.platform
                    })
                    logger.info(f"找到有效證書: {cert.attributes.name} (ID: {cert.id})")
            
            if not valid_certs:
                logger.error(f"未找到類型為 {cert_type} 的有效證書")
                return None
            
            # 選擇過期日期最遠的證書（最安全的選擇）
            valid_certs.sort(key=lambda x: x['expiration_date'], reverse=True)
            selected_cert = valid_certs[0]
            logger.info(f"選擇證書: {selected_cert['name']} (ID: {selected_cert['id']})")
            logger.info(f"證書過期日期: {selected_cert['expiration_date']}")
            
            # 檢查證書是否即將過期（30天內）
            exp_date_str = selected_cert['expiration_date']
            if isinstance(exp_date_str, str):
                exp_date = datetime.fromisoformat(exp_date_str.replace('Z', '+00:00'))
            else:
                exp_date = exp_date_str
            
            days_until_expiry = (exp_date - current_time).days
            if days_until_expiry < 30:
                logger.warning(f"⚠️  警告：選擇的證書將在 {days_until_expiry} 天後過期！")
                logger.warning(f"⚠️  建議盡快更新證書")
            
            return selected_cert
            
        except EndpointException as e:
            logger.error(f"獲取證書時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
            return None
        except Exception as e:
            logger.error(f"獲取證書時發生未知錯誤: {e}")
            return None
    
    def find_all_provisioning_profiles(self, profile_name: str, include_invalid: bool = True) -> List[Dict[str, Any]]:
        """根據名稱尋找所有 Provisioning Profile（可能有重複）
        
        Args:
            profile_name: Profile 名稱
            include_invalid: 是否包含 INVALID 狀態的 Profile（已過期但未刪除）
        """
        logger.info(f"尋找名稱為 '{profile_name}' 的所有 Provisioning Profile...")
        if include_invalid:
            logger.info("（包含已過期/無效的 Profile）")
        
        try:
            # 獲取所有 Profile 並手動過濾
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/profiles"
            headers = dict(self.connection._s.headers)
            profiles = []
            
            # Try multiple methods to find profiles
            # Method 1: Search using name filter
            params = {"filter[name]": profile_name, "limit": 200}
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Method 2: If not found, try searching INVALID state profiles
            if not data.get('data') and include_invalid:
                params = {"filter[name]": profile_name, "filter[profileState]": "INVALID", "limit": 200}
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
            
            if data.get('data'):
                for profile in data['data']:
                    profile_state = profile['attributes'].get('profileState', 'UNKNOWN')
                    profile_id = profile['id']
                    logger.info(f"Found profile: {profile['attributes']['name']} (ID: {profile_id}, State: {profile_state})")
                    
                    profile_info = {
                        'id': profile_id,
                        'name': profile['attributes']['name'],
                        'profile_type': profile['attributes']['profileType'],
                        'platform': profile['attributes']['platform'],
                        'state': profile_state,
                        'bundle_id': None,
                        'certificates': [],
                        'devices': []
                    }
                    profiles.append(profile_info)
            
            # Method 3: If still not found, iterate through all profiles
            if not profiles and include_invalid:
                next_url = url
                page_count = 0
                while next_url and page_count < 10:
                    page_count += 1
                    response = requests.get(next_url, headers=headers, params={"limit": 200})
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('data'):
                        for profile in data['data']:
                            profile_api_name = profile['attributes']['name']
                            profile_state = profile['attributes'].get('profileState', 'UNKNOWN')
                            
                            if profile_api_name == profile_name:
                                profile_id = profile['id']
                                logger.info(f"Found matching profile: {profile_api_name} (ID: {profile_id}, State: {profile_state})")
                                
                                profile_info = {
                                    'id': profile_id,
                                    'name': profile['attributes']['name'],
                                    'profile_type': profile['attributes']['profileType'],
                                    'platform': profile['attributes']['platform'],
                                    'state': profile_state,
                                    'bundle_id': None,
                                    'certificates': [],
                                    'devices': []
                                }
                                profiles.append(profile_info)
                    
                    next_url = data.get('links', {}).get('next')
            
            logger.info(f"Found {len(profiles)} profile(s) with the same name")
            return profiles
                
        except Exception as e:
            logger.error(f"獲取 Provisioning Profile 時發生未知錯誤: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def find_provisioning_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """根據名稱尋找 Provisioning Profile"""
        logger.info(f"尋找名稱為 '{profile_name}' 的 Provisioning Profile...")
        
        try:
            # 使用 requests 直接搜索，繞過分頁限制
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/profiles"
            params = {"filter[name]": profile_name}
            headers = dict(self.connection._s.headers)
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('data'):
                profile = data['data'][0]
                profile_id = profile['id']
                logger.info(f"找到現有 Profile: {profile['attributes']['name']} (ID: {profile_id})")
                
                # 獲取詳細資訊包括關聯資源
                detail_url = f"https://api.appstoreconnect.apple.com/v1/profiles/{profile_id}"
                detail_params = {"include": "bundleId,certificates,devices"}
                detail_response = requests.get(detail_url, headers=headers, params=detail_params)
                detail_response.raise_for_status()
                detail_data = detail_response.json()
                
                profile_info = {
                    'id': profile_id,
                    'name': profile['attributes']['name'],
                    'profile_type': profile['attributes']['profileType'],
                    'platform': profile['attributes']['platform'],
                    'bundle_id': None,
                    'certificates': [],
                    'devices': []
                }
                
                # 解析關聯資源
                if detail_data.get('included'):
                    for included_item in detail_data['included']:
                        if included_item['type'] == 'bundleIds':
                            profile_info['bundle_id'] = included_item['id']
                        elif included_item['type'] == 'certificates':
                            profile_info['certificates'].append(included_item['id'])
                        elif included_item['type'] == 'devices':
                            profile_info['devices'].append(included_item['id'])
                
                return profile_info
            
            logger.info(f"未找到名稱為 '{profile_name}' 的 Provisioning Profile")
            return None
            
        except EndpointException as e:
            logger.error(f"獲取 Provisioning Profile 時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
            return None
        except Exception as e:
            logger.error(f"獲取 Provisioning Profile 時發生未知錯誤: {e}")
            return None
    
    def delete_provisioning_profile(self, profile_id: str) -> bool:
        """刪除 Provisioning Profile"""
        logger.info(f"刪除 Provisioning Profile (ID: {profile_id})...")
        
        try:
            self.connection.profile(profile_id).delete()
            logger.info(f"成功刪除 Provisioning Profile (ID: {profile_id})")
            return True
            
        except EndpointException as e:
            logger.error(f"刪除 Provisioning Profile 時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
            return False
        except Exception as e:
            logger.error(f"刪除 Provisioning Profile 時發生未知錯誤: {e}")
            return False
    
    def get_all_devices(self) -> List[str]:
        """獲取所有可用設備的 ID 列表"""
        logger.info("獲取所有可用設備...")
        
        try:
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/devices"
            headers = dict(self.connection._s.headers)
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            device_ids = [device['id'] for device in data.get('data', [])]
            
            logger.info(f"找到 {len(device_ids)} 個設備")
            return device_ids
                
        except requests.RequestException as e:
            logger.error(f"獲取設備列表時發生 HTTP 錯誤: {e}")
            return []
        except Exception as e:
            logger.error(f"獲取設備列表時發生未知錯誤: {e}")
            return []
    
    def find_bundle_id_by_identifier(self, bundle_identifier: str) -> Optional[str]:
        """根據 Bundle Identifier 尋找 Bundle ID"""
        logger.info(f"尋找 Bundle ID: {bundle_identifier}...")
        
        try:
            # 直接使用 requests 來繞過 pydantic 驗證問題
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/bundleIds"
            params = {"filter[identifier]": bundle_identifier}
            
            # 使用 connection 的 session headers
            headers = dict(self.connection._s.headers)
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('data'):
                bundle_id = data['data'][0]['id']
                logger.info(f"找到 Bundle ID: {bundle_id}")
                return bundle_id
            else:
                logger.error(f"未找到 Bundle ID: {bundle_identifier}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"獲取 Bundle ID 時發生 HTTP 錯誤: {e}")
            return None
        except Exception as e:
            logger.error(f"獲取 Bundle ID 時發生未知錯誤: {e}")
            return None
    
    def create_provisioning_profile(self, profile_name: str, profile_type: str, 
                                   bundle_id: str, cert_id: str, 
                                   device_ids: List[str] = None) -> Optional[str]:
        """建立新的 Provisioning Profile"""
        logger.info(f"建立新的 Provisioning Profile: {profile_name}")
        logger.info(f"- Profile Type: {profile_type}")
        logger.info(f"- Bundle ID: {bundle_id}")
        logger.info(f"- Certificate ID: {cert_id}")
        if device_ids:
            logger.info(f"- Device IDs: {device_ids}")
        
        try:
            # 建立請求物件
            relationships_data = {
                'bundle_id': {
                    'data': {
                        'type': 'bundleIds',
                        'id': bundle_id
                    }
                },
                'certificates': {
                    'data': [
                        {
                            'type': 'certificates',
                            'id': cert_id
                        }
                    ]
                }
            }
            
            # 如果有裝置 ID，加入到關聯中（通常用於開發用 Profile）
            if device_ids:
                relationships_data['devices'] = {
                    'data': [
                        {
                            'type': 'devices',
                            'id': device_id
                        } for device_id in device_ids
                    ]
                }
            
            # 建立 Profile
            create_request = ProfileCreateRequest(
                data=ProfileCreateRequest.Data(
                    attributes=ProfileCreateRequest.Data.Attributes(
                        name=profile_name,
                        profile_type=profile_type
                    ),
                    relationships=ProfileCreateRequest.Data.Relationships(
                        **relationships_data
                    )
                )
            )
            
            response = self.connection.profiles().create(create_request)
            
            if response.data:
                new_profile_id = response.data.id
                logger.info(f"成功建立 Provisioning Profile (ID: {new_profile_id})")
                return new_profile_id
            else:
                logger.error("建立 Provisioning Profile 失敗：回應中沒有資料")
                return None
                
        except EndpointException as e:
            logger.error(f"建立 Provisioning Profile 時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
            return None
        except Exception as e:
            logger.error(f"建立 Provisioning Profile 時發生未知錯誤: {e}")
            return None


def decode_private_key(private_key_base64: str) -> str:
    """解碼 Base64 編碼的私鑰"""
    try:
        decoded_bytes = base64.b64decode(private_key_base64)
        return decoded_bytes.decode('utf-8')
    except Exception as e:
        logger.error(f"解碼私鑰失敗: {e}")
        raise


def set_github_output(name: str, value: str):
    """設置 GitHub Action 輸出"""
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")
        logger.info(f"設置輸出 {name}={value}")


def main():
    """主要函數"""
    logger.info("=== App Store Provision Profile Upsert 開始執行 ===")
    
    # 獲取輸入參數
    profile_name = os.environ.get('PROFILE_NAME')
    cert_type = os.environ.get('CERT_TYPE')
    issuer_id = os.environ.get('ISSUER_ID')
    key_id = os.environ.get('KEY_ID')
    private_key_base64 = os.environ.get('PRIVATE_KEY_BASE64')
    bundle_id_identifier = os.environ.get('BUNDLE_ID')
    profile_type = os.environ.get('PROFILE_TYPE', 'IOS_APP_DEVELOPMENT')
    
    # 驗證必要參數
    required_params = {
        'PROFILE_NAME': profile_name,
        'CERT_TYPE': cert_type,
        'ISSUER_ID': issuer_id,
        'KEY_ID': key_id,
        'PRIVATE_KEY_BASE64': private_key_base64,
        'BUNDLE_ID': bundle_id_identifier,
        'PROFILE_TYPE': profile_type
    }
    
    missing_params = [key for key, value in required_params.items() if not value]
    if missing_params:
        logger.error(f"缺少必要參數: {', '.join(missing_params)}")
        set_github_output('success', 'false')
        sys.exit(1)
    
    logger.info(f"輸入參數:")
    logger.info(f"- Profile Name: {profile_name}")
    logger.info(f"- Certificate Type: {cert_type}")
    logger.info(f"- Bundle ID: {bundle_id_identifier}")
    logger.info(f"- Profile Type: {profile_type}")
    
    try:
        # 解碼私鑰
        private_key = decode_private_key(private_key_base64)
        
        # 建立管理器
        manager = ProvisioningProfileManager(issuer_id, key_id, private_key)
        
        # 步驟 1: 尋找可用證書
        logger.info("\n=== 步驟 1: 尋找可用證書 ===")
        certificate = manager.find_available_certificate(cert_type)
        if not certificate:
            logger.error("未找到可用證書，任務結束")
            set_github_output('success', 'false')
            sys.exit(1)
        
        cert_id = certificate['id']
        set_github_output('cert_id', cert_id)
        
        # 步驟 2: 尋找 Bundle ID
        logger.info("\n=== 步驟 2: 尋找 Bundle ID ===")
        bundle_id = manager.find_bundle_id_by_identifier(bundle_id_identifier)
        if not bundle_id:
            logger.error("未找到對應的 Bundle ID，任務結束")
            set_github_output('success', 'false')
            sys.exit(1)
        
        # 步驟 3: 檢查現有 Provisioning Profile（可能有多個重複）
        logger.info("\n=== 步驟 3: 檢查現有 Provisioning Profile ===")
        existing_profiles = manager.find_all_provisioning_profiles(profile_name)
        
        device_ids = []
        if existing_profiles:
            logger.info(f"找到 {len(existing_profiles)} 個現有 Profile，準備全部刪除...")
            # 保存第一個 Profile 的裝置資訊（如果有的話）
            device_ids = existing_profiles[0].get('devices', [])
            
            # 刪除所有同名 Profile
            for profile in existing_profiles:
                logger.info(f"刪除 Profile: {profile['name']} (ID: {profile['id']})")
                if not manager.delete_provisioning_profile(profile['id']):
                    logger.error(f"刪除 Profile {profile['id']} 失敗，任務結束")
                    set_github_output('success', 'false')
                    sys.exit(1)
        else:
            logger.info("未找到現有 Profile，將建立新的")
        
        # 對於 Ad Hoc 或 Development profile，需要設備列表
        if profile_type in ['IOS_APP_ADHOC', 'IOS_APP_DEVELOPMENT', 'MAC_APP_DEVELOPMENT'] and not device_ids:
            logger.info("此 Profile 類型需要設備列表，正在獲取所有可用設備...")
            device_ids = manager.get_all_devices()
            if not device_ids:
                logger.warning("未找到任何設備，但仍嘗試建立 Profile")
        
        # 步驟 4: 建立新的 Provisioning Profile
        logger.info("\n=== 步驟 4: 建立新的 Provisioning Profile ===")
        new_profile_id = manager.create_provisioning_profile(
            profile_name=profile_name,
            profile_type=profile_type,
            bundle_id=bundle_id,
            cert_id=cert_id,
            device_ids=device_ids if device_ids else None
        )
        
        # 如果建立失敗，檢查是否是因為重複名稱（可能有隱藏的已過期 Profile）
        if not new_profile_id:
            logger.warning("⚠️  建立失敗，可能存在已過期但未完全刪除的同名 Profile")
            logger.warning("⚠️  建議方案：")
            logger.warning("   1. 在 Apple Developer 網站手動刪除所有同名 Profile")
            logger.warning("   2. 或者修改 PROFILE_NAME，例如加上日期: 'Cpo AdHoc 2025'")
            logger.warning("   3. 等待幾小時後再試（讓 Apple 系統完全清除舊記錄）")
            logger.error("建立新 Profile 失敗")
            set_github_output('success', 'false')
            sys.exit(1)
        
        logger.info(f"✅ 成功完成 Provisioning Profile 更新")
        logger.info(f"- Profile ID: {new_profile_id}")
        logger.info(f"- Certificate ID: {cert_id}")
        
        set_github_output('profile_id', new_profile_id)
        set_github_output('success', 'true')
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {e}")
        set_github_output('success', 'false')
        sys.exit(1)
    
    logger.info("=== App Store Provision Profile Upsert 執行完成 ===")


if __name__ == "__main__":
    main()
