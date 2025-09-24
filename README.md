# App Store Provision Profile Upsert Action

這是一個 GitHub Action，用於使用 Applaud 套件來更新或建立 App Store Connect 的 Provisioning Profile。

## 功能特色

- 🔍 根據證書類型自動尋找可用的證書
- 🔄 智能更新：如果 Provisioning Profile 已存在則先刪除再重建
- 📝 保持原有設定：重建時保留原有的 Bundle ID 和裝置設定
- 🛡️ 錯誤處理：完整的錯誤處理和日誌記錄
- 🔐 安全性：支援 Base64 編碼的私鑰輸入

## 使用方法

### 基本用法

```yaml
name: Update Provisioning Profile
on:
  workflow_dispatch:
    inputs:
      profile_name:
        description: 'Provisioning Profile 名稱'
        required: true
        type: string

jobs:
  update-profile:
    runs-on: ubuntu-latest
    steps:
      - name: Update Provisioning Profile
        uses: ./appstore-provision-profile-upsert
        with:
          profile_name: ${{ github.event.inputs.profile_name }}
          cert_type: 'IOS_DISTRIBUTION'
          issuer_id: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          key_id: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          private_key_base64: ${{ secrets.APP_STORE_CONNECT_PRIVATE_KEY_BASE64 }}
          bundle_id: 'com.example.myapp'
          profile_type: 'IOS_APP_STORE'
```

### 完整範例

```yaml
name: iOS App Store Deployment
on:
  push:
    tags:
      - 'v*'

jobs:
  update-provisioning:
    runs-on: ubuntu-latest
    outputs:
      profile-id: ${{ steps.update-profile.outputs.profile_id }}
      cert-id: ${{ steps.update-profile.outputs.cert_id }}
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Update Provisioning Profile
        id: update-profile
        uses: ./appstore-provision-profile-upsert
        with:
          profile_name: 'MyApp Production Profile'
          cert_type: 'IOS_DISTRIBUTION'
          issuer_id: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          key_id: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          private_key_base64: ${{ secrets.APP_STORE_CONNECT_PRIVATE_KEY_BASE64 }}
          bundle_id: 'com.nextdrive.myapp'
          profile_type: 'IOS_APP_STORE'
      
      - name: Use Profile Information
        run: |
          echo "Profile ID: ${{ steps.update-profile.outputs.profile_id }}"
          echo "Certificate ID: ${{ steps.update-profile.outputs.cert_id }}"
          echo "Success: ${{ steps.update-profile.outputs.success }}"

  build:
    needs: update-provisioning
    if: needs.update-provisioning.outputs.success == 'true'
    runs-on: macos-latest
    steps:
      # 使用更新的 Provisioning Profile 進行建置...
      - name: Build with Updated Profile
        run: |
          echo "Building with Profile ID: ${{ needs.update-provisioning.outputs.profile-id }}"
```

## 輸入參數

| 參數 | 描述 | 必要 | 預設值 | 範例 |
|------|------|------|--------|------|
| `profile_name` | Provisioning Profile 名稱 | ✅ | - | `MyApp Production Profile` |
| `cert_type` | 證書類型 | ✅ | - | `IOS_DISTRIBUTION` |
| `issuer_id` | App Store Connect API Issuer ID | ✅ | - | `69a6de8a-1234-47e3-e053-5b8c7c11a4d1` |
| `key_id` | App Store Connect API Key ID | ✅ | - | `ABCDEFGHIJ` |
| `private_key_base64` | API 私鑰 (Base64 編碼) | ✅ | - | `LS0tLS1CRUdJTi...` |
| `bundle_id` | App Bundle ID | ✅ | - | `com.example.myapp` |
| `profile_type` | Provisioning Profile 類型 | ❌ | `IOS_APP_DEVELOPMENT` | `IOS_APP_STORE` |

### 證書類型 (cert_type)

支援的證書類型包括：
- `IOS_DEVELOPMENT` - iOS 開發證書
- `IOS_DISTRIBUTION` - iOS 分發證書
- `MAC_APP_DEVELOPMENT` - macOS 開發證書
- `MAC_APP_DISTRIBUTION` - macOS 分發證書
- `MAC_INSTALLER_DISTRIBUTION` - macOS 安裝程式分發證書

### Profile 類型 (profile_type)

支援的 Profile 類型包括：
- `IOS_APP_DEVELOPMENT` - iOS 開發用 Profile
- `IOS_APP_STORE` - iOS App Store 分發用 Profile
- `IOS_APP_ADHOC` - iOS Ad Hoc 分發用 Profile
- `MAC_APP_DEVELOPMENT` - macOS 開發用 Profile
- `MAC_APP_STORE` - macOS App Store 分發用 Profile

## 輸出參數

| 參數 | 描述 | 範例 |
|------|------|------|
| `profile_id` | 建立或更新的 Provisioning Profile ID | `30RBP47T2T` |
| `cert_id` | 使用的證書 ID | `30RBP47T2T` |
| `success` | 操作是否成功 | `true` 或 `false` |

## 設置步驟

### 1. 建立 App Store Connect API Key

1. 登入 [App Store Connect](https://appstoreconnect.apple.com)
2. 進入 **Users and Access** > **Integrations** > **App Store Connect API**
3. 點擊 **Generate API Key**
4. 選擇 **Admin** 或 **App Manager** 角色
5. 下載 `.p8` 私鑰檔案並記錄 **Key ID** 和 **Issuer ID**

### 2. 準備私鑰

將下載的 `.p8` 檔案轉換為 Base64 格式：

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy
```

### 3. 設置 GitHub Secrets

在您的 Repository 中設置以下 Secrets：

- `APP_STORE_CONNECT_ISSUER_ID`: Issuer ID
- `APP_STORE_CONNECT_KEY_ID`: Key ID  
- `APP_STORE_CONNECT_PRIVATE_KEY_BASE64`: Base64 編碼的私鑰

## 工作流程

此 Action 執行以下步驟：

1. **🔍 尋找可用證書**
   - 根據指定的證書類型尋找有效證書
   - 檢查證書是否未過期
   - 如果找不到有效證書則結束任務

2. **📋 檢查現有 Profile** 
   - 根據名稱尋找是否存在同名的 Provisioning Profile
   - 如果存在，保存相關設定資訊（Bundle ID、裝置列表等）

3. **🗑️ 刪除現有 Profile**
   - 如果找到現有 Profile，先將其刪除
   - 準備使用相同設定建立新的 Profile

4. **🔨 建立新 Profile**
   - 使用找到的證書建立新的 Provisioning Profile  
   - 保持原有的 Bundle ID 和裝置設定
   - 使用最新的證書

## 錯誤處理

此 Action 包含完整的錯誤處理機制：

- ✅ API 連接錯誤處理
- ✅ 證書驗證和過期檢查  
- ✅ 權限不足錯誤提示
- ✅ 詳細的日誌輸出
- ✅ 失敗時設置適當的退出碼

## 需求

- Python 3.11+
- 有效的 App Store Connect API Key
- Admin 或 App Manager 權限

## 授權

MIT License

## 貢獻

歡迎提交 Pull Request 或 Issue！

---

**注意**: 此 Action 會刪除並重建 Provisioning Profile，請確保您有適當的備份和權限。
