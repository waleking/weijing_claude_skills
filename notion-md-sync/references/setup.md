# Notion Markdown Sync - Setup Guide

## Prerequisites

1. **Python 3.x** with `requests` module
2. **Notion Integration Token**
3. **Notion pages shared with your integration**

## Getting Your Notion API Token

### Step 1: Create a Notion Integration

1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Give it a name (e.g., "Markdown Sync")
4. Select the workspace
5. Click "Submit"

### Step 2: Get Your Token

1. After creating the integration, you'll see the "Internal Integration Token"
2. Click "Show" and copy the token (starts with `ntn_`)
3. **Important**: Keep this token secure - treat it like a password

### Step 3: Share Pages with Integration

Your integration needs access to pages:

1. Open the Notion page where you want to sync markdown files
2. Click the "..." menu in the top right
3. Go to "Connections" or "Add connections"
4. Find and select your integration
5. The integration now has access to this page and its children

## Setting the Token

### Option 1: Environment Variable (Recommended)

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export NOTION_TOKEN="ntn_your_token_here"
```

Then reload your shell:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### Option 2: Inline (For One-Time Use)

```bash
NOTION_TOKEN="ntn_your_token_here" python3 sync_md_to_notion.py file.md
```

### Option 3: Session Variable (Temporary)

```bash
export NOTION_TOKEN="ntn_your_token_here"
python3 sync_md_to_notion.py file.md
```

## Verifying Setup

Test your setup:

```bash
# Create a test markdown file
echo "# Test\n\nHello Notion!" > test.md

# Run the sync script
python3 ~/.claude/skills/notion-md-sync/scripts/sync_md_to_notion.py test.md
```

If successful, you'll see:
- "Using parent page: [page name]"
- "✓ Uploaded X blocks"
- A Notion URL

## Troubleshooting

### "NOTION_TOKEN environment variable is not set"
- The token is not configured. Follow "Setting the Token" above.

### "No parent page found"
- The script couldn't find a suitable parent page
- Solution: Provide a parent page ID manually in the script (line ~343)
- Or ensure your pages are shared with the integration

### "HTTP 401 Unauthorized"
- Token is invalid or expired
- Verify you copied the full token (starts with `ntn_`)
- Regenerate token from https://www.notion.so/my-integrations

### "HTTP 403 Forbidden"
- Integration doesn't have access to the page
- Share the target page with your integration (Step 3 above)

## Security Best Practices

1. **Never commit tokens to git**: Add `NOTION_TOKEN` to `.gitignore`
2. **Use environment variables**: Don't hardcode tokens in scripts
3. **Limit integration scope**: Only share necessary pages
4. **Rotate tokens periodically**: Generate new tokens every few months
5. **Use separate tokens**: Different projects = different integrations
