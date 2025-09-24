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
    from applaud.endpoints.certificates import CertificateListEndpoint
    from applaud.endpoints.profiles import ProfileListEndpoint, ProfileCreateRequest
    from applaud.models.certificate_type import CertificateType
    from applaud.models.profile_type import ProfileType
    from applaud.exceptions import EndpointException
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
            certificates = self.connection.certificates().filter(
                certificate_type=cert_type
            ).get()
            
            valid_certs = []
            current_time = datetime.now(timezone.utc)
            
            for cert in certificates.data:
                # 檢查證書是否過期
                exp_date_str = cert.attributes.expiration_date
                exp_date = datetime.fromisoformat(exp_date_str.replace('Z', '+00:00'))
                
                if exp_date > current_time:
                    valid_certs.append({
                        'id': cert.id,
                        'name': cert.attributes.name,
                        'display_name': cert.attributes.display_name,
                        'expiration_date': exp_date_str,
                        'platform': cert.attributes.platform
                    })
                    logger.info(f"找到有效證書: {cert.attributes.name} (ID: {cert.id})")
            
            if not valid_certs:
                logger.error(f"未找到類型為 {cert_type} 的有效證書")
                return None
            
            # 返回第一個有效證書
            selected_cert = valid_certs[0]
            logger.info(f"選擇證書: {selected_cert['name']} (ID: {selected_cert['id']})")
            return selected_cert
            
        except EndpointException as e:
            logger.error(f"獲取證書時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
            return None
        except Exception as e:
            logger.error(f"獲取證書時發生未知錯誤: {e}")
            return None
    
    def find_provisioning_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """根據名稱尋找 Provisioning Profile"""
        logger.info(f"尋找名稱為 '{profile_name}' 的 Provisioning Profile...")
        
        try:
            # 列出所有 Provisioning Profiles
            profiles = self.connection.profiles().get()
            
            for profile in profiles.data:
                if profile.attributes.name == profile_name:
                    logger.info(f"找到現有 Profile: {profile.attributes.name} (ID: {profile.id})")
                    
                    # 獲取詳細資訊包括關聯資源
                    detailed_profile = self.connection.profile(profile.id).include([
                        ProfileListEndpoint.Include.BUNDLE_ID,
                        ProfileListEndpoint.Include.CERTIFICATES,
                        ProfileListEndpoint.Include.DEVICES
                    ]).get()
                    
                    profile_info = {
                        'id': profile.id,
                        'name': profile.attributes.name,
                        'profile_type': profile.attributes.profile_type,
                        'platform': profile.attributes.platform,
                        'bundle_id': None,
                        'certificates': [],
                        'devices': []
                    }
                    
                    # 解析關聯資源
                    if hasattr(detailed_profile, 'included') and detailed_profile.included:
                        for included_item in detailed_profile.included:
                            if included_item.type == 'bundleIds':
                                profile_info['bundle_id'] = included_item.id
                            elif included_item.type == 'certificates':
                                profile_info['certificates'].append(included_item.id)
                            elif included_item.type == 'devices':
                                profile_info['devices'].append(included_item.id)
                    
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
    
    def find_bundle_id_by_identifier(self, bundle_identifier: str) -> Optional[str]:
        """根據 Bundle Identifier 尋找 Bundle ID"""
        logger.info(f"尋找 Bundle ID: {bundle_identifier}...")
        
        try:
            bundle_ids = self.connection.bundle_ids().filter(
                identifier=bundle_identifier
            ).get()
            
            if bundle_ids.data:
                bundle_id_obj = bundle_ids.data[0]
                logger.info(f"找到 Bundle ID: {bundle_id_obj.id}")
                return bundle_id_obj.id
            else:
                logger.error(f"未找到 Bundle ID: {bundle_identifier}")
                return None
                
        except EndpointException as e:
            logger.error(f"獲取 Bundle ID 時發生錯誤: {e}")
            for error in e.errors:
                logger.error(f"- {error.code}: {error.detail}")
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
        
        # 步驟 3: 檢查現有 Provisioning Profile
        logger.info("\n=== 步驟 3: 檢查現有 Provisioning Profile ===")
        existing_profile = manager.find_provisioning_profile(profile_name)
        
        device_ids = []
        if existing_profile:
            logger.info("找到現有 Profile，準備刪除...")
            # 保存裝置資訊（如果有的話）
            device_ids = existing_profile.get('devices', [])
            
            # 刪除現有 Profile
            if not manager.delete_provisioning_profile(existing_profile['id']):
                logger.error("刪除現有 Profile 失敗，任務結束")
                set_github_output('success', 'false')
                sys.exit(1)
        else:
            logger.info("未找到現有 Profile，將建立新的")
        
        # 步驟 4: 建立新的 Provisioning Profile
        logger.info("\n=== 步驟 4: 建立新的 Provisioning Profile ===")
        new_profile_id = manager.create_provisioning_profile(
            profile_name=profile_name,
            profile_type=profile_type,
            bundle_id=bundle_id,
            cert_id=cert_id,
            device_ids=device_ids if device_ids else None
        )
        
        if new_profile_id:
            logger.info(f"✅ 成功完成 Provisioning Profile 更新")
            logger.info(f"- Profile ID: {new_profile_id}")
            logger.info(f"- Certificate ID: {cert_id}")
            
            set_github_output('profile_id', new_profile_id)
            set_github_output('success', 'true')
        else:
            logger.error("建立新 Profile 失敗")
            set_github_output('success', 'false')
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"執行過程中發生錯誤: {e}")
        set_github_output('success', 'false')
        sys.exit(1)
    
    logger.info("=== App Store Provision Profile Upsert 執行完成 ===")


if __name__ == "__main__":
    main()
