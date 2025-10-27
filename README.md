# App Store Provisioning Profile Upsert Action

A GitHub Action to automatically update or create App Store Connect Provisioning Profiles.

## Usage

### Basic Usage (Create/Update Profile)

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

### Advanced Usage (Download Profile)

```yaml
name: Update and Download Provisioning Profile
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
      - name: Checkout
        uses: actions/checkout@v4

      - name: Update Provisioning Profile
        id: renew_profile
        uses: nextDriveIoE/appstore-provision-profile-upsert@main
        with:
          profile_name: ${{ github.event.inputs.profile_name }}
          cert_type: 'IOS_DISTRIBUTION'
          issuer_id: ${{ secrets.APP_STORE_CONNECT_ISSUER_ID }}
          key_id: ${{ secrets.APP_STORE_CONNECT_KEY_ID }}
          private_key_base64: ${{ secrets.APP_STORE_CONNECT_PRIVATE_KEY_BASE64 }}
          bundle_id: 'com.example.myapp'
          profile_type: 'IOS_APP_STORE'
          out_path: './provisioning_profiles/${{ github.event.inputs.profile_name }}.mobileprovision'

      - name: Display Results
        run: |
          echo "Profile ID: ${{ steps.renew_profile.outputs.profile_id }}"
          echo "Certificate ID: ${{ steps.renew_profile.outputs.cert_id }}"
          echo "Profile Path: ${{ steps.renew_profile.outputs.profile_path }}"
          echo "Success: ${{ steps.renew_profile.outputs.success }}"

      - name: Upload Profile as Artifact
        if: success()
        uses: actions/upload-artifact@v3
        with:
          name: provisioning-profile
          path: ${{ steps.renew_profile.outputs.profile_path }}

      - name: Store Profile in Secret (Optional)
        if: success()
        run: |
          echo "PROVISIONING_PROFILE_BASE64=${{ steps.renew_profile.outputs.provision_profile_base64 }}" >> $GITHUB_ENV
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
| `out_path` | Output path for downloaded provisioning profile | ❌ | - | `./provisioning_profiles/MyProfile.mobileprovision` |

**Common Values:**
- `cert_type`: `IOS_DEVELOPMENT`, `IOS_DISTRIBUTION`, `MAC_APP_DISTRIBUTION`
- `profile_type`: `IOS_APP_DEVELOPMENT`, `IOS_APP_STORE`, `IOS_APP_ADHOC`

## Output Parameters

| Output | Description | Example |
|--------|-------------|---------|
| `profile_id` | ID of the created/updated provisioning profile | `7TH5ULYJQG` |
| `cert_id` | ID of the certificate used | `AA59HGVWC5` |
| `profile_path` | Path to the downloaded provisioning profile (if `out_path` is specified) | `./provisioning_profiles/MyProfile.mobileprovision` |
| `provision_profile_base64` | Base64-encoded content of the provisioning profile | `MII21AYJKoZIhvcNAQcCoII2xTCCNsE...` |
| `success` | Whether the operation was successful | `true` or `false` |

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
