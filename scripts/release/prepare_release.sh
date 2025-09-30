#!/bin/bash
# Prepare Release Script
# Automates release preparation process

set -e

VERSION=$1
if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 1.0.0"
    exit 1
fi

echo "Preparing release v${VERSION}"
echo "=============================="

# Step 1: Version validation
echo -e "\n[1/7] Validating version format..."
if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid version format. Use semantic versioning (e.g., 1.0.0)"
    exit 1
fi
echo "✓ Version format valid"

# Step 2: Check working directory clean
echo -e "\n[2/7] Checking git status..."
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Working directory not clean. Commit or stash changes."
    exit 1
fi
echo "✓ Working directory clean"

# Step 3: Run all tests
echo -e "\n[3/7] Running test suite..."
pytest tests/ -v --tb=short -m "not slow and not hardware"
if [ $? -ne 0 ]; then
    echo "ERROR: Tests failed. Fix issues before release."
    exit 1
fi
echo "✓ All tests passed"

# Step 4: Update version in files
echo -e "\n[4/7] Updating version numbers..."
# Update version in relevant files
echo "__version__ = '${VERSION}'" > src/version.py
echo "✓ Version updated"

# Step 5: Generate changelog
echo -e "\n[5/7] Generating changelog..."
cat > CHANGELOG_${VERSION}.md << EOF
# Release v${VERSION}

**Release Date**: $(date +%Y-%m-%d)

## New Features
- [List new features]

## Bug Fixes
- [List bug fixes]

## Performance Improvements
- [List performance improvements]

## Breaking Changes
- [List breaking changes if any]

## Known Issues
- [List known issues]

## Upgrade Notes
- [Instructions for upgrading]
EOF
echo "✓ Changelog template created: CHANGELOG_${VERSION}.md"
echo "Please edit the changelog with release details"

# Step 6: Create release branch
echo -e "\n[6/7] Creating release branch..."
git checkout -b release/v${VERSION}
git add src/version.py CHANGELOG_${VERSION}.md
git commit -m "chore: prepare release v${VERSION}"
echo "✓ Release branch created: release/v${VERSION}"

# Step 7: Instructions
echo -e "\n[7/7] Next steps:"
echo "1. Edit CHANGELOG_${VERSION}.md with release details"
echo "2. git add CHANGELOG_${VERSION}.md && git commit --amend"
echo "3. git push origin release/v${VERSION}"
echo "4. Create pull request to main branch"
echo "5. After merge, create GitHub release with tag v${VERSION}"
echo "6. CI/CD will automatically build and deploy"

echo -e "\n✓ Release preparation complete!"