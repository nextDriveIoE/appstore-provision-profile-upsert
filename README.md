# App Store Provisioning Profile Upsert Action

A GitHub Action to automatically update or create App Store Connect Provisioning Profiles.

## Usage

```yaml
name: Update Provisioning Profile
on:
  workflow_dispatch:
    inputs:
      profile_name:
        description: 'Provisioning Profile Name'
        required: true
        type: string

jobs:
  update-profile:
    runs-on: ubuntu-latest
    steps:
      - name: Update Provisioning Profile
        uses: nextDriveIoE/appstore-provision-profile-upsert@main
        with:
          profile_name: ${{ github.event.inputs.profile_name }}
          cert_type: 'IOS_DISTRIBUTION'
          issuer_id: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          key_id: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          private_key_base64: ${{ secrets.APP_STORE_CONNECT_PRIVATE_KEY_BASE64 }}
          bundle_id: 'com.example.myapp'
          profile_type: 'IOS_APP_STORE'
```

## Input Parameters

| Parameter | Description | Required | Default | Example |
|------|------|------|--------|------|
| `profile_name` | Provisioning Profile name | ✅ | - | `MyApp Production Profile` |
| `cert_type` | Certificate type | ✅ | - | `IOS_DISTRIBUTION` |
| `issuer_id` | App Store Connect API Issuer ID | ✅ | - | `69a6de8a-1234-47e3-e053-5b8c7c11a4d1` |
| `key_id` | App Store Connect API Key ID | ✅ | - | `ABCDEFGHIJ` |
| `private_key_base64` | API Private Key (Base64 encoded) | ✅ | - | `LS0tLS1CRUdJTi...` |
| `bundle_id` | App Bundle ID | ✅ | - | `com.example.myapp` |
| `profile_type` | Provisioning Profile type | ❌ | `IOS_APP_DEVELOPMENT` | `IOS_APP_STORE` |

**Common Values:**
- `cert_type`: `IOS_DEVELOPMENT`, `IOS_DISTRIBUTION`, `MAC_APP_DISTRIBUTION`
- `profile_type`: `IOS_APP_DEVELOPMENT`, `IOS_APP_STORE`, `IOS_APP_ADHOC`

## Setup

1. **Create API Key** at [App Store Connect](https://appstoreconnect.apple.com) → Users and Access → Integrations
2. **Convert private key** to Base64: `base64 -i AuthKey_XXX.p8 | pbcopy`
3. **Add GitHub Secrets**:
   - `APP_STORE_CONNECT_ISSUER_ID`
   - `APP_STORE_CONNECT_KEY_ID`
   - `APP_STORE_CONNECT_PRIVATE_KEY_BASE64`

## Local Testing

```bash
cp .env.example .env
# Edit .env with your credentials
python run_local.py
```

## License

MIT License

---

**Note**: This Action deletes and recreates profiles. Ensure you have backups and proper permissions.
