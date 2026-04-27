#!/bin/bash
set -e

GITHUB_USER="frcarlo"
REPO="ha-fritz-profiles"

# Read token
read -rsp "GitHub Token: " TOKEN
echo

# Set remote with token
git remote set-url origin "https://${GITHUB_USER}:${TOKEN}@github.com/${GITHUB_USER}/${REPO}.git"

# Get current version from manifest.json
CURRENT=$(grep '"version"' custom_components/fritz_profiles/manifest.json | grep -o '[0-9]*\.[0-9]*\.[0-9]*')
echo "Aktuelle Version: $CURRENT"

# Ask for new version
read -rp "Neue Version (Enter = kein neuer Tag): " NEW_VERSION

if [[ -n "$NEW_VERSION" ]]; then
    # Update manifest.json
    sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" custom_components/fritz_profiles/manifest.json
    echo "manifest.json aktualisiert: $CURRENT → $NEW_VERSION"

    git add custom_components/fritz_profiles/manifest.json
    git commit -m "Bump version to $NEW_VERSION"

    git tag "v$NEW_VERSION"
    echo "Tag v$NEW_VERSION erstellt"
fi

# Push commits and all tags
git push origin main --tags
echo "Done!"

# Clear token from remote URL
git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO}.git"
