#!/usr/bin/env bash
set -euo pipefail
umask 077

: "${APPLE_TEAM_ID:?Set APPLE_TEAM_ID in the testflight environment}"
: "${IOS_BUNDLE_ID:?Set IOS_BUNDLE_ID in the testflight environment}"
: "${IOS_DISTRIBUTION_P12:?Set the base64 distribution certificate secret}"
: "${IOS_DISTRIBUTION_PASSWORD:?Set the distribution certificate password secret}"
: "${IOS_APP_STORE_PROFILE:?Set the base64 App Store provisioning profile secret}"
: "${APP_STORE_CONNECT_KEY:?Set the base64 App Store Connect API key secret}"
: "${APP_STORE_CONNECT_KEY_ID:?Set APP_STORE_CONNECT_KEY_ID in the testflight environment}"
: "${APP_STORE_CONNECT_ISSUER_ID:?Set APP_STORE_CONNECT_ISSUER_ID in the testflight environment}"
: "${GITHUB_RUN_NUMBER:?Run this script from the GitHub Actions workflow}"
: "${GITHUB_RUN_ATTEMPT:?Run this script from the GitHub Actions workflow}"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
keychain="$work/signing.keychain-db"
keychain_password=$(openssl rand -hex 24)

printf '%s' "$IOS_DISTRIBUTION_P12" | base64 -D > "$work/distribution.p12"
printf '%s' "$IOS_APP_STORE_PROFILE" | base64 -D > "$work/profile.mobileprovision"
printf '%s' "$APP_STORE_CONNECT_KEY" | base64 -D > "$work/AuthKey_${APP_STORE_CONNECT_KEY_ID}.p8"

security create-keychain -p "$keychain_password" "$keychain"
security set-keychain-settings -lut 1200 "$keychain"
security unlock-keychain -p "$keychain_password" "$keychain"
security import "$work/distribution.p12" -P "$IOS_DISTRIBUTION_PASSWORD" -A -t cert -f pkcs12 -k "$keychain"
security set-key-partition-list -S apple-tool:,apple: -s -k "$keychain_password" "$keychain" >/dev/null
security list-keychains -d user -s "$keychain"
security cms -D -i "$work/profile.mobileprovision" > "$work/profile.plist"

python3 - "$work" <<'PY'
from pathlib import Path
import os
import plistlib
import shutil
import sys

work = Path(sys.argv[1])
team = os.environ['APPLE_TEAM_ID']
bundle = os.environ['IOS_BUNDLE_ID']
with (work / 'profile.plist').open('rb') as source:
    profile = plistlib.load(source)
if profile['Entitlements'].get('application-identifier') != f'{team}.{bundle}':
    raise SystemExit('The provisioning profile does not match the Apple team and bundle ID.')
profile_dir = Path.home() / 'Library/Developer/Xcode/UserData/Provisioning Profiles'
profile_dir.mkdir(parents=True, exist_ok=True)
shutil.copyfile(work / 'profile.mobileprovision', profile_dir / f"{profile['UUID']}.mobileprovision")
with (work / 'ExportOptions.plist').open('wb') as output:
    plistlib.dump({
        'destination': 'upload',
        'manageAppVersionAndBuildNumber': False,
        'method': 'app-store-connect',
        'provisioningProfiles': {bundle: profile['UUID']},
        'signingCertificate': 'Apple Distribution',
        'signingStyle': 'manual',
        'teamID': team,
    }, output)
(work / 'profile-id').write_text(profile['UUID'])
PY

xcodebuild -project ios/ClipBridge.xcodeproj -scheme ClipBridge \
  -configuration Release -destination 'generic/platform=iOS' \
  -archivePath "$work/ClipBridge.xcarchive" \
  CODE_SIGN_STYLE=Manual CODE_SIGN_IDENTITY='Apple Distribution' \
  DEVELOPMENT_TEAM="$APPLE_TEAM_ID" PRODUCT_BUNDLE_IDENTIFIER="$IOS_BUNDLE_ID" \
  PROVISIONING_PROFILE_SPECIFIER="$(cat "$work/profile-id")" \
  CURRENT_PROJECT_VERSION="$GITHUB_RUN_NUMBER.$GITHUB_RUN_ATTEMPT" archive

xcodebuild -exportArchive -archivePath "$work/ClipBridge.xcarchive" \
  -exportOptionsPlist "$work/ExportOptions.plist" -exportPath "$work/export" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$work/AuthKey_${APP_STORE_CONNECT_KEY_ID}.p8" \
  -authenticationKeyID "$APP_STORE_CONNECT_KEY_ID" \
  -authenticationKeyIssuerID "$APP_STORE_CONNECT_ISSUER_ID"
