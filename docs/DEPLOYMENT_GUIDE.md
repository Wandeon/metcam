# Team Deployment Guide - FootballVision Pro

## Overview
This guide explains how to push your team's work to the GitHub repository following the established workflow.

---

## Prerequisites

Before you start, ensure you have:
- ✅ Completed all assigned components for your team
- ✅ All code committed to your local feature branches
- ✅ Comprehensive documentation (README.md in each component)
- ✅ Tests passing
- ✅ Working in the metcam repository: `/home/admin/metcam`

---

## Deployment Steps

### Step 1: Navigate to Repository

```bash
cd /home/admin/metcam
```

### Step 2: Verify Your Work

Check that all your work is committed:

```bash
# Check current branch
git branch --show-current

# View your commits
git log --oneline | head -20

# Check for uncommitted changes
git status
```

**Expected**: Clean working tree, all changes committed.

### Step 3: Switch to Develop Branch

```bash
git checkout develop
git pull origin develop  # Get latest changes
```

### Step 4: Merge Your Feature Branches

If you worked on multiple feature branches (like W1-W10), merge them:

```bash
# Example for Infrastructure Team (adapt to your team)
git merge --no-ff feature/your-component-1 -m "Merge: Your Component 1"
git merge --no-ff feature/your-component-2 -m "Merge: Your Component 2"
# ... continue for all your feature branches
```

**Alternative**: If all work is already in develop (like after cherry-picking), skip to Step 5.

### Step 5: Verify Branch Status

```bash
# Check how many commits ahead of remote
git status

# View what will be pushed
git log origin/develop..develop --oneline
```

### Step 6: Push to GitHub

**⚠️ IMPORTANT: SSH Deploy Key Issue**

The repository has SSH deploy keys that may be read-only. If SSH push fails, use HTTPS instead.

#### Try SSH First:

```bash
git push origin develop
```

#### If SSH Fails (Permission Denied Error):

Switch to HTTPS and retry:

```bash
# Switch remote URL to HTTPS
git remote set-url origin https://github.com/Wandeon/metcam.git

# Push using HTTPS
git push origin develop
```

**Note**: HTTPS authentication will use cached credentials from the system.

### Step 7: Verify Push Success

Confirm your code is on GitHub:

```bash
# Check remote branch
git log origin/develop --oneline | head -10

# Verify sync
git status
```

**Expected Output**: `Your branch is up to date with 'origin/develop'`

---

## Team-Specific Examples

### Video Pipeline Team (W11-W20)

```bash
cd /home/admin/metcam
git checkout develop
git pull origin develop

# Merge your feature branches
git merge --no-ff feature/camera-capture -m "Merge: Camera capture system"
git merge --no-ff feature/encoding -m "Merge: Video encoding pipeline"
git merge --no-ff feature/streaming -m "Merge: RTSP streaming"
# ... merge all W11-W20 components

# Push (use HTTPS if SSH fails)
git push origin develop

# Verify
git log origin/develop --oneline | head -10
```

### Processing Team (W21-W30)

```bash
cd /home/admin/metcam
git checkout develop
git pull origin develop

# Merge your feature branches
git merge --no-ff feature/calibration -m "Merge: Camera calibration"
git merge --no-ff feature/stitching -m "Merge: Panoramic stitching"
git merge --no-ff feature/compression -m "Merge: Video compression"
# ... merge all W21-W30 components

# Push (use HTTPS if SSH fails)
git push origin develop

# Verify
git log origin/develop --oneline | head -10
```

### Platform Team (W31-W40)

```bash
cd /home/admin/metcam
git checkout develop
git pull origin develop

# Merge your feature branches
git merge --no-ff feature/web-interface -m "Merge: Web interface"
git merge --no-ff feature/rest-api -m "Merge: REST API"
git merge --no-ff feature/cloud-integration -m "Merge: Cloud upload"
# ... merge all W31-W40 components

# Push (use HTTPS if SSH fails)
git push origin develop

# Verify
git log origin/develop --oneline | head -10
```

### Quality Team (W41-W50)

```bash
cd /home/admin/metcam
git checkout develop
git pull origin develop

# Merge your feature branches
git merge --no-ff feature/test-strategy -m "Merge: Test strategy"
git merge --no-ff feature/integration-tests -m "Merge: Integration tests"
git merge --no-ff feature/performance-tests -m "Merge: Performance tests"
# ... merge all W41-W50 components

# Push (use HTTPS if SSH fails)
git push origin develop

# Verify
git log origin/develop --oneline | head -10
```

---

## Troubleshooting

### Issue: "Permission denied" when pushing via SSH

**Solution**: Switch to HTTPS

```bash
git remote set-url origin https://github.com/Wandeon/metcam.git
git push origin develop
```

### Issue: "Your branch is behind origin/develop"

**Solution**: Pull and rebase

```bash
git pull origin develop --rebase
git push origin develop
```

### Issue: Merge conflicts

**Solution**: Resolve conflicts manually

```bash
# Identify conflicting files
git status

# Edit conflicting files
# Look for <<<<<<< HEAD markers

# After resolving
git add <conflicting-files>
git commit -m "Resolve merge conflicts"
git push origin develop
```

### Issue: "Authentication failed" with HTTPS

**Solution**: Check credentials

```bash
# Clear credential cache
git credential reject protocol=https host=github.com

# Try push again (will prompt for credentials)
git push origin develop
```

### Issue: Accidentally pushed to wrong branch

**Solution**: Contact Queen immediately - DO NOT force push

---

## Post-Push Verification Checklist

After pushing, verify everything is correct:

```bash
# 1. Check remote log
git log origin/develop --oneline | head -20

# 2. Verify your commits are present
git log origin/develop --grep="your-team-name\|W[0-9]" --oneline

# 3. Check file structure on remote
git ls-tree -r --name-only origin/develop | grep "src/your-team/"

# 4. Confirm branch sync
git status
# Should say: "Your branch is up to date with 'origin/develop'"
```

---

## Notification to Queen

After successful push, send notification via Telegram:

```bash
# Use MCP Telegram tool (if available in your session)
# Or manually report via team communication channel
```

**Message Template**:

```
✅ [TEAM NAME] - DEPLOYMENT COMPLETE

Status: Successfully pushed to GitHub

Components Delivered:
- W##: [Component Name]
- W##: [Component Name]
- ... (list all your components)

Metrics:
- Total Commits: [number]
- Lines of Code: [approximate]
- Files Created: [number]

Repository: github.com/Wandeon/metcam
Branch: develop
Status: ✅ Pushed and verified

All [TEAM NAME] work is now on GitHub and ready for Queen review.
```

---

## Git Workflow Summary

```
1. Work on feature branches
   └── feature/your-component

2. Commit regularly
   └── git commit -m "feat(team): descriptive message"

3. Switch to develop
   └── git checkout develop

4. Merge your work
   └── git merge --no-ff feature/your-component

5. Push to GitHub
   └── git push origin develop (or HTTPS if SSH fails)

6. Verify
   └── git log origin/develop

7. Notify Queen
   └── Send completion message
```

---

## Commit Message Convention

Follow this format for all commits:

```
<type>(<scope>): <description>

[optional body]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

**Scopes**:
- `infrastructure`: W1-W10
- `video-pipeline`: W11-W20
- `processing`: W21-W30
- `platform`: W31-W40
- `quality`: W41-W50

**Examples**:

```bash
git commit -m "feat(video-pipeline): W11 camera capture with dual IMX477"
git commit -m "feat(processing): W23 GPU-accelerated stitching"
git commit -m "feat(platform): W35 real-time status dashboard"
git commit -m "docs(quality): Complete testing strategy documentation"
```

---

## Security Notes

- ✅ **DO**: Push code, documentation, tests
- ✅ **DO**: Include configuration templates
- ❌ **DON'T**: Push secrets, API keys, passwords
- ❌ **DON'T**: Push large binary files (>10MB)
- ❌ **DON'T**: Push temporary/debug files
- ❌ **DON'T**: Force push to develop branch

**Before pushing, check**:

```bash
# Look for common secret patterns
git diff origin/develop..develop | grep -iE "(password|api_key|secret|token)" || echo "No secrets found"

# Check file sizes
git diff --stat origin/develop..develop
```

---

## Quick Reference Commands

```bash
# Status check
git status
git branch --show-current
git log --oneline | head -10

# Switch to develop
git checkout develop
git pull origin develop

# Merge work
git merge --no-ff feature/your-component -m "Merge: Your component"

# Push (SSH)
git push origin develop

# Push (HTTPS if SSH fails)
git remote set-url origin https://github.com/Wandeon/metcam.git
git push origin develop

# Verify
git log origin/develop --oneline | head -10
git status
```

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check git status**: `git status` often shows what's wrong
2. **View error messages**: Read the full error output
3. **Check logs**: `git log --oneline --graph --all`
4. **Ask Queen**: Report via Telegram with:
   - What you were trying to do
   - Full error message
   - Output of `git status`

---

## Success Criteria

Your deployment is successful when:

- ✅ `git status` shows: "Your branch is up to date with 'origin/develop'"
- ✅ `git log origin/develop` shows your commits
- ✅ No uncommitted changes in `git status`
- ✅ All team components visible in remote branch
- ✅ Queen notified of completion

---

## Example: Complete Deployment Session

```bash
# 1. Navigate
cd /home/admin/metcam

# 2. Check status
git status
git branch --show-current  # Should be 'develop'

# 3. Verify commits
git log --oneline | head -20

# 4. Check what will be pushed
git log origin/develop..develop --oneline
echo "Commits to push: $(git rev-list --count origin/develop..develop)"

# 5. Push (try SSH first)
git push origin develop

# 6. If SSH fails, use HTTPS
git remote set-url origin https://github.com/Wandeon/metcam.git
git push origin develop

# 7. Verify success
git log origin/develop --oneline | head -10
git status

# 8. Expected output
# Your branch is up to date with 'origin/develop'.
# nothing to commit, working tree clean

# ✅ SUCCESS!
```

---

## Final Notes

- **Timeline**: Push your work as soon as all components are complete and tested
- **Coordination**: Check with other teams if you see conflicts
- **Documentation**: Ensure all README.md files are comprehensive
- **Testing**: Run all tests before pushing
- **Review**: Self-review your commits before pushing

**Good luck with your deployment!** 🚀

---

**Document Version**: 1.0
**Last Updated**: 2025-09-30
**Created By**: Infrastructure Team
**For**: All FootballVision Pro Development Teams