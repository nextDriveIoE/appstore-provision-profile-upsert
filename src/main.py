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
            # 直接使用 requests 來繞過 pydantic 驗證問題
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/certificates"
            headers = dict(self.connection._s.headers)
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            valid_certs = []
            current_time = datetime.now(timezone.utc)
            
            for cert in data.get('data', []):
                # 過濾證書類型
                if cert['attributes']['certificateType'] != cert_type:
                    continue
                    
                # 檢查證書是否過期
                exp_date_str = cert['attributes']['expirationDate']
                exp_date = datetime.fromisoformat(exp_date_str.replace('Z', '+00:00'))
                
                if exp_date > current_time:
                    cert_info = {
                        'id': cert['id'],
                        'name': cert['attributes']['name'],
                        'display_name': cert['attributes'].get('displayName', cert['attributes']['name']),
                        'expiration_date': exp_date.isoformat(),
                        'platform': cert['attributes'].get('platform', 'IOS')
                    }
                    valid_certs.append(cert_info)
                    logger.info(f"找到有效證書: {cert_info['name']} (ID: {cert_info['id']})")
            
            if not valid_certs:
                logger.error(f"未找到類型為 {cert_type} 的有效證書")
                return None
            
            # 選擇過期日期最遠的證書（最安全的選擇）
            valid_certs.sort(key=lambda x: x['expiration_date'], reverse=True)
            selected_cert = valid_certs[0]
            logger.info(f"選擇證書: {selected_cert['name']} (ID: {selected_cert['id']})")
            logger.info(f"證書過期日期: {selected_cert['expiration_date']}")
            
            # 檢查證書是否即將過期（30天內）
            exp_date = datetime.fromisoformat(selected_cert['expiration_date'].replace('Z', '+00:00'))
            days_until_expiry = (exp_date - current_time).days
            if days_until_expiry < 30:
                logger.warning(f"⚠️  警告：選擇的證書將在 {days_until_expiry} 天後過期！")
                logger.warning(f"⚠️  建議盡快更新證書")
            
            return selected_cert
            
        except requests.RequestException as e:
            logger.error(f"獲取證書時發生 HTTP 錯誤: {e}")
            return None
        except Exception as e:
            logger.error(f"獲取證書時發生未知錯誤: {e}")
            import traceback
            traceback.print_exc()
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
            # 直接使用 requests 來繞過 pydantic 驗證問題
            import requests
            url = f"https://api.appstoreconnect.apple.com/v1/profiles/{profile_id}"
            headers = dict(self.connection._s.headers)
            
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            
            logger.info(f"成功刪除 Provisioning Profile (ID: {profile_id})")
            return True
            
        except requests.RequestException as e:
            logger.error(f"刪除 Provisioning Profile 時發生 HTTP 錯誤: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            logger.error(f"- {error.get('code', 'UNKNOWN')}: {error.get('detail', 'No detail')}")
                except:
                    logger.error(f"- Response status: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"刪除 Provisioning Profile 時發生未知錯誤: {e}")
            import traceback
            traceback.print_exc()
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
    
    def download_provisioning_profile(self, profile_id: str, output_path: str, max_retries: int = 3, retry_delay: int = 5) -> bool:
        """下載 Provisioning Profile 並保存到指定路徑
        
        Args:
            profile_id: Profile ID
            output_path: 輸出路徑
            max_retries: 最大重試次數
            retry_delay: 重試延遲（秒）
        """
        logger.info(f"下載 Provisioning Profile (ID: {profile_id}) 到 {output_path}...")
        
        try:
            import requests
            import time
            # 使用正確的 API 端點來獲取 profile 內容
            url = f"https://api.appstoreconnect.apple.com/v1/profiles/{profile_id}"
            headers = dict(self.connection._s.headers)
            
            # 重試機制：確保 profile 已完全建立
            response = None
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()
                    break  # 成功則跳出迴圈
                except requests.exceptions.HTTPError as e:
                    if response and response.status_code == 404 and attempt < max_retries - 1:
                        logger.warning(f"Profile 尚未完全建立，{retry_delay} 秒後重試... (嘗試 {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                    else:
                        raise
            
            if response is None:
                logger.error("無法下載 Provisioning Profile")
                return False
            
            # 從 API 回應中提取 profile 內容
            data = response.json()
            if not data.get('data'):
                logger.error("API 回應中沒有 profile 資料")
                return False
            
            profile_data = data['data']
            # profileContent 是 Base64 編碼的內容
            profile_content_b64 = profile_data.get('attributes', {}).get('profileContent')
            if not profile_content_b64:
                logger.error("無法從 API 回應中取得 profileContent")
                return False
            
            # 解碼 Base64 內容
            import base64
            profile_content = base64.b64decode(profile_content_b64)
            
            # 確保輸出目錄存在
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"已建立輸出目錄: {output_dir}")
            
            # 保存 provisioning profile
            with open(output_path, 'wb') as f:
                f.write(profile_content)
            
            logger.info(f"成功下載 Provisioning Profile 到 {output_path}")
            logger.info(f"檔案大小: {len(profile_content)} bytes")
            return True
            
        except requests.RequestException as e:
            logger.error(f"下載 Provisioning Profile 時發生 HTTP 錯誤: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            logger.error(f"- {error.get('code', 'UNKNOWN')}: {error.get('detail', 'No detail')}")
                except:
                    logger.error(f"- Response status: {e.response.status_code}")
            return False
        except Exception as e:
            logger.error(f"下載 Provisioning Profile 時發生未知錯誤: {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
            # 直接使用 requests 來繞過 pydantic 驗證問題
            import requests
            url = "https://api.appstoreconnect.apple.com/v1/profiles"
            headers = dict(self.connection._s.headers)
            
            # 建立請求資料
            relationships = {
                'bundleId': {
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
                relationships['devices'] = {
                    'data': [
                        {
                            'type': 'devices',
                            'id': device_id
                        } for device_id in device_ids
                    ]
                }
            
            payload = {
                'data': {
                    'type': 'profiles',
                    'attributes': {
                        'name': profile_name,
                        'profileType': profile_type
                    },
                    'relationships': relationships
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('data'):
                new_profile_id = data['data']['id']
                logger.info(f"成功建立 Provisioning Profile (ID: {new_profile_id})")
                return new_profile_id
            else:
                logger.error("建立 Provisioning Profile 失敗：回應中沒有資料")
                return None
                
        except requests.RequestException as e:
            logger.error(f"建立 Provisioning Profile 時發生 HTTP 錯誤: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    if 'errors' in error_data:
                        for error in error_data['errors']:
                            logger.error(f"- {error.get('code', 'UNKNOWN')}: {error.get('detail', 'No detail')}")
                except:
                    logger.error(f"- Response status: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"建立 Provisioning Profile 時發生未知錯誤: {e}")
            import traceback
            traceback.print_exc()
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
    """設置 GitHub Action 輸出
    
    使用 GitHub Actions 的多行輸出格式：
    name=value
    或者對於包含換行符的值：
    name<<EOF
    value
    EOF
    
    注意：此函數不會拋出異常，只會記錄錯誤，確保程式繼續執行
    """
    github_output = os.environ.get('GITHUB_OUTPUT')
    if not github_output:
        logger.warning(f"⚠️  GITHUB_OUTPUT 環境變數未設置，無法設置輸出 {name}")
        return False
    
    try:
        # 確保輸出目錄存在
        output_dir = os.path.dirname(github_output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"✅ 建立輸出目錄: {output_dir}")
        
        # 使用 GitHub Actions 的多行輸出格式
        # 這樣可以支持包含特殊字符和換行符的值
        delimiter = f"EOF_{name}_{int(os.urandom(4).hex(), 16)}"
        
        with open(github_output, 'a') as f:
            # 如果值包含換行符或特殊字符，使用多行格式
            if '\n' in value or '\r' in value:
                f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")
                logger.info(f"✅ 設置輸出 {name} (多行格式，長度: {len(value)} 字元)")
            else:
                f.write(f"{name}={value}\n")
                # 對於長值，只顯示前 100 字元
                display_value = value[:100] + "..." if len(value) > 100 else value
                logger.info(f"✅ 設置輸出 {name}={display_value}")
        
        # 驗證輸出是否被正確寫入
        with open(github_output, 'r') as f:
            content = f.read()
            if name in content:
                logger.info(f"✅ 輸出驗證成功: {name} 已寫入 {github_output}")
                return True
            else:
                logger.error(f"❌ 輸出驗證失敗: {name} 未找到在 {github_output}")
                return False
                
    except Exception as e:
        error_msg = f"❌ 設置輸出失敗: {e}"
        logger.error(error_msg)
        import traceback
        traceback.print_exc()
        return False


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
    out_path = os.environ.get('OUT_PATH')
    
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
        # 在 renew 時，總是獲取所有可用設備，確保包含所有裝置
        if profile_type in ['IOS_APP_ADHOC', 'IOS_APP_DEVELOPMENT', 'MAC_APP_DEVELOPMENT']:
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
        
        # 步驟 5: 下載 Provisioning Profile 並生成 Base64
        logger.info("\n=== 步驟 5: 下載 Provisioning Profile ===")
        
        # 決定臨時下載路徑
        download_path = out_path if out_path else tempfile.NamedTemporaryFile(delete=False, suffix='.mobileprovision').name
        logger.info(f"下載路徑: {download_path}")
        
        if manager.download_provisioning_profile(new_profile_id, download_path):
            logger.info(f"✅ 成功下載 Provisioning Profile 到 {download_path}")
            
            # 驗證檔案是否存在且有內容
            if not os.path.exists(download_path):
                error_msg = f"❌ 檔案寫入失敗：檔案不存在 {download_path}"
                logger.error(error_msg)
                set_github_output('success', 'false')
                raise FileNotFoundError(error_msg)
            
            file_size = os.path.getsize(download_path)
            if file_size == 0:
                error_msg = f"❌ 檔案寫入失敗：檔案大小為 0 bytes {download_path}"
                logger.error(error_msg)
                set_github_output('success', 'false')
                raise ValueError(error_msg)
            
            logger.info(f"✅ 檔案驗證成功，大小: {file_size} bytes")
            
            # 如果指定了 out_path，設置 profile_path 輸出
            if out_path:
                set_github_output('profile_path', out_path)
                logger.info(f"✅ 設置 profile_path 輸出: {out_path}")
            
            # 將檔案轉換成 Base64
            logger.info("正在將 Provisioning Profile 轉換為 Base64...")
            try:
                with open(download_path, 'rb') as f:
                    profile_content = f.read()
                
                if not profile_content:
                    error_msg = "❌ Base64 轉換失敗：檔案內容為空"
                    logger.error(error_msg)
                    set_github_output('success', 'false')
                    raise ValueError(error_msg)
                
                logger.info(f"✅ 檔案讀取成功，大小: {len(profile_content)} bytes")
                
                # 移除所有空白字符（換行符、空格等），確保 GitHub Actions 能正確處理
                profile_base64 = base64.b64encode(profile_content).decode('utf-8').replace('\n', '').replace(' ', '')
                
                if not profile_base64:
                    error_msg = "❌ Base64 轉換失敗：Base64 字符串為空"
                    logger.error(error_msg)
                    set_github_output('success', 'false')
                    raise ValueError(error_msg)
                
                logger.info(f"✅ Base64 編碼成功，長度: {len(profile_base64)} 字元")
                
                set_github_output('provision_profile_base64', profile_base64)
                logger.info(f"✅ 成功設置 provision_profile_base64 輸出")
                logger.info(f"✅ 成功轉換為 Base64 (長度: {len(profile_base64)} 字元)")
            except Exception as e:
                error_msg = f"❌ 轉換 Base64 失敗: {e}"
                logger.error(error_msg)
                import traceback
                traceback.print_exc()
                set_github_output('success', 'false')
                raise
            
            # 清理臨時檔案（如果沒有指定 out_path）
            if not out_path:
                try:
                    os.unlink(download_path)
                    logger.info(f"✅ 已清理臨時檔案: {download_path}")
                except Exception as e:
                    logger.warning(f"⚠️  清理臨時檔案失敗: {e}")
        else:
            error_msg = "❌ 下載 Provisioning Profile 失敗"
            logger.error(error_msg)
            set_github_output('success', 'false')
            raise RuntimeError(error_msg)
        
        set_github_output('profile_id', new_profile_id)
        set_github_output('success', 'true')
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {e}")
        set_github_output('success', 'false')
        sys.exit(1)
    
    logger.info("=== App Store Provision Profile Upsert 執行完成 ===")


if __name__ == "__main__":
    main()
