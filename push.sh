#!/bin/bash
set -e

# Get current version from manifest.json
CURRENT=$(grep '"version"' custom_components/fritz_profiles/manifest.json | grep -o '[0-9]*\.[0-9]*\.[0-9]*')
echo "Aktuelle Version: $CURRENT"

# Ask for new version
read -rp "Neue Version (Enter = nur pushen ohne neuen Release): " NEW_VERSION

if [[ -n "$NEW_VERSION" ]]; then
    sed -i "s/\"version\": \"$CURRENT\"/\"version\": \"$NEW_VERSION\"/" custom_components/fritz_profiles/manifest.json
    echo "manifest.json aktualisiert: $CURRENT → $NEW_VERSION"

    git add custom_components/fritz_profiles/manifest.json
    git commit -m "Bump version to $NEW_VERSION"

    git tag "v$NEW_VERSION"
    echo "Tag v$NEW_VERSION erstellt"
fi

git push origin main --tags

# Create GitHub Release (HACS requires releases, not just tags)
if [[ -n "$NEW_VERSION" ]]; then
    gh release create "v$NEW_VERSION" \
        --title "v$NEW_VERSION" \
        --generate-notes
    echo "GitHub Release v$NEW_VERSION erstellt"
fi

echo "Done!"
