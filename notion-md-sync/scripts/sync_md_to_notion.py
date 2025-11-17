#!/usr/bin/env python3
"""
Batch sync Markdown files to Notion using the Notion API.

This script converts Markdown files to Notion pages, handling:
- Tables (converted to Notion table blocks)
- Code blocks (converted to Notion code blocks)
- Headings, paragraphs, lists
- Automatic parent page detection

Usage:
    python sync_md_to_notion.py file1.md file2.md ...
    python sync_md_to_notion.py *.md
"""

import os
import sys
import re
import json
import requests
from typing import List, Dict, Any, Optional

# Get Notion token from environment
# Set NOTION_TOKEN environment variable before running:
#   export NOTION_TOKEN="ntn_your_token_here"
# Or pass it inline:
#   NOTION_TOKEN="ntn_your_token_here" python3 sync_md_to_notion.py file.md
NOTION_TOKEN = os.environ.get('NOTION_TOKEN')

if not NOTION_TOKEN:
    print("ERROR: NOTION_TOKEN environment variable is not set.")
    print("\nPlease set your Notion API token:")
    print("  export NOTION_TOKEN='ntn_your_token_here'")
    print("\nTo get your token:")
    print("  1. Go to https://www.notion.so/my-integrations")
    print("  2. Create a new integration or use existing one")
    print("  3. Copy the 'Internal Integration Token'")
    print("  4. Share target pages with the integration")
    sys.exit(1)

NOTION_API_BASE = 'https://api.notion.com/v1'
HEADERS = {
    'Authorization': f'Bearer {NOTION_TOKEN}',
    'Content-Type': 'application/json',
    'Notion-Version': '2022-06-28'
}


def search_notion_pages(query: str) -> List[Dict[str, Any]]:
    """Search for Notion pages by query."""
    response = requests.post(
        f'{NOTION_API_BASE}/search',
        headers=HEADERS,
        json={'query': query, 'filter': {'property': 'object', 'value': 'page'}}
    )
    response.raise_for_status()
    return response.json().get('results', [])


def create_notion_page(parent_id: str, title: str) -> str:
    """Create a new Notion page and return its ID."""
    response = requests.post(
        f'{NOTION_API_BASE}/pages',
        headers=HEADERS,
        json={
            'parent': {'page_id': parent_id},
            'properties': {
                'title': [{'type': 'text', 'text': {'content': title}}]
            }
        }
    )
    response.raise_for_status()
    return response.json()['id']


def append_blocks(page_id: str, blocks: List[Dict[str, Any]]) -> None:
    """Append blocks to a Notion page."""
    response = requests.patch(
        f'{NOTION_API_BASE}/blocks/{page_id}/children',
        headers=HEADERS,
        json={'children': blocks}
    )
    response.raise_for_status()


def parse_rich_text(text: str) -> List[Dict[str, Any]]:
    """Parse Markdown text into Notion rich text with formatting."""
    rich_text = []
    i = 0

    while i < len(text):
        # Bold text **text**
        if text[i:i+2] == '**':
            end = text.find('**', i+2)
            if end != -1:
                content = text[i+2:end]
                rich_text.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': {'bold': True, 'italic': False, 'strikethrough': False,
                                   'underline': False, 'code': False, 'color': 'default'}
                })
                i = end + 2
                continue

        # Inline code `text`
        if text[i] == '`' and (i == 0 or text[i-1] != '`'):
            end = text.find('`', i+1)
            if end != -1 and (end+1 >= len(text) or text[end+1] != '`'):
                content = text[i+1:end]
                rich_text.append({
                    'type': 'text',
                    'text': {'content': content},
                    'annotations': {'bold': False, 'italic': False, 'strikethrough': False,
                                   'underline': False, 'code': True, 'color': 'default'}
                })
                i = end + 1
                continue

        # Links [text](url)
        if text[i] == '[':
            close_bracket = text.find(']', i)
            if close_bracket != -1 and close_bracket + 1 < len(text) and text[close_bracket + 1] == '(':
                close_paren = text.find(')', close_bracket + 2)
                if close_paren != -1:
                    link_text = text[i+1:close_bracket]
                    url = text[close_bracket+2:close_paren]
                    rich_text.append({
                        'type': 'text',
                        'text': {'content': link_text, 'link': {'url': url}},
                        'annotations': {'bold': False, 'italic': False, 'strikethrough': False,
                                       'underline': False, 'code': False, 'color': 'default'}
                    })
                    i = close_paren + 1
                    continue

        # Regular text - collect until next special character
        next_special = len(text)
        for special_pos in [text.find('**', i), text.find('`', i), text.find('[', i)]:
            if special_pos != -1 and special_pos < next_special:
                next_special = special_pos

        if next_special == i:
            # Single character that didn't match patterns above
            if rich_text and 'link' not in rich_text[-1]['text'] and not any(rich_text[-1]['annotations'].values()):
                rich_text[-1]['text']['content'] += text[i]
            else:
                rich_text.append({
                    'type': 'text',
                    'text': {'content': text[i]},
                    'annotations': {'bold': False, 'italic': False, 'strikethrough': False,
                                   'underline': False, 'code': False, 'color': 'default'}
                })
            i += 1
        else:
            # Regular text segment
            content = text[i:next_special]
            if content:
                if rich_text and 'link' not in rich_text[-1]['text'] and not any(rich_text[-1]['annotations'].values()):
                    rich_text[-1]['text']['content'] += content
                else:
                    rich_text.append({
                        'type': 'text',
                        'text': {'content': content},
                        'annotations': {'bold': False, 'italic': False, 'strikethrough': False,
                                       'underline': False, 'code': False, 'color': 'default'}
                    })
            i = next_special

    # If no rich text was created, return plain text
    if not rich_text:
        rich_text = [{'type': 'text', 'text': {'content': text}}]

    return rich_text


def parse_markdown_table(lines: List[str]) -> Optional[Dict[str, Any]]:
    """Parse a Markdown table into a Notion table block."""
    if len(lines) < 2:
        return None

    # Parse header row
    header_cells = [cell.strip() for cell in lines[0].split('|') if cell.strip()]
    if not header_cells:
        return None

    table_width = len(header_cells)

    # Skip separator line (line[1])
    # Parse data rows
    rows = []

    # Add header row
    rows.append({
        'type': 'table_row',
        'table_row': {
            'cells': [[{'type': 'text', 'text': {'content': cell}}] for cell in header_cells]
        }
    })

    # Add data rows
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.split('|') if cell.strip()]
        if len(cells) == table_width:
            rows.append({
                'type': 'table_row',
                'table_row': {
                    'cells': [[{'type': 'text', 'text': {'content': cell}}] for cell in cells]
                }
            })

    return {
        'type': 'table',
        'table': {
            'table_width': table_width,
            'has_column_header': True,
            'has_row_header': False,
            'children': rows
        }
    }


def markdown_to_notion_blocks(md_content: str) -> List[Dict[str, Any]]:
    """Convert Markdown content to Notion blocks."""
    lines = md_content.split('\n')
    blocks = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.startswith('```'):
            language = line[3:].strip() or 'plain text'
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                code_lines.append(lines[i])
                i += 1
            blocks.append({
                'type': 'code',
                'code': {
                    'rich_text': [{'type': 'text', 'text': {'content': '\n'.join(code_lines)}}],
                    'language': language
                }
            })
            i += 1
            continue

        # Tables
        if '|' in line and i + 1 < len(lines) and '|' in lines[i + 1]:
            # Collect table lines
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                table_lines.append(lines[i])
                i += 1

            table_block = parse_markdown_table(table_lines)
            if table_block:
                blocks.append(table_block)
            continue

        # Headings
        if line.startswith('### '):
            blocks.append({
                'type': 'heading_3',
                'heading_3': {'rich_text': parse_rich_text(line[4:])}
            })
        elif line.startswith('## '):
            blocks.append({
                'type': 'heading_2',
                'heading_2': {'rich_text': parse_rich_text(line[3:])}
            })
        elif line.startswith('# '):
            # Use heading_2 since heading_1 isn't supported
            blocks.append({
                'type': 'heading_2',
                'heading_2': {'rich_text': parse_rich_text(line[2:])}
            })

        # Bulleted lists
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                'type': 'bulleted_list_item',
                'bulleted_list_item': {'rich_text': parse_rich_text(line[2:])}
            })

        # Numbered lists (convert to bulleted since numbered isn't well supported)
        elif re.match(r'^\d+\.\s', line):
            content = re.sub(r'^\d+\.\s', '', line)
            blocks.append({
                'type': 'bulleted_list_item',
                'bulleted_list_item': {'rich_text': parse_rich_text(content)}
            })

        # Paragraphs
        elif line.strip():
            blocks.append({
                'type': 'paragraph',
                'paragraph': {'rich_text': parse_rich_text(line)}
            })

        i += 1

    return blocks


def sync_markdown_file(md_file: str, parent_page_id: Optional[str] = None) -> str:
    """Sync a Markdown file to Notion."""
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # Extract title from filename
    title = os.path.splitext(os.path.basename(md_file))[0].replace('_', ' ')

    # Find parent page if not provided
    if not parent_page_id:
        # Try to find a relevant parent page
        search_query = ' '.join(title.split()[:2])  # Use first 2 words
        pages = search_notion_pages(search_query)
        if pages:
            parent_page_id = pages[0]['id']
            print(f"  Using parent page: {pages[0].get('properties', {}).get('title', {}).get('title', [{}])[0].get('plain_text', 'Unknown')}")
        else:
            print(f"  ERROR: No parent page found. Please provide parent_page_id.")
            return None

    # Create Notion page
    print(f"  Creating page: {title}")
    page_id = create_notion_page(parent_page_id, title)

    # Convert markdown to blocks
    blocks = markdown_to_notion_blocks(md_content)

    # Upload in chunks (max 100 blocks per request)
    chunk_size = 100
    for i in range(0, len(blocks), chunk_size):
        chunk = blocks[i:i + chunk_size]
        print(f"  Uploading blocks {i+1}-{min(i+chunk_size, len(blocks))} of {len(blocks)}")
        append_blocks(page_id, chunk)

    page_url = f"https://www.notion.so/{page_id.replace('-', '')}"
    print(f"  ✓ Uploaded {len(blocks)} blocks")
    print(f"  URL: {page_url}")
    return page_url


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync Markdown files to Notion with formatting preservation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync with auto-detected parent
  python sync_md_to_notion.py file1.md file2.md

  # Sync to specific parent page
  python sync_md_to_notion.py --parent 2aee6057-c0cb-815b-ac5f-dd80e1c07d39 file.md

  # Sync all markdown files
  python sync_md_to_notion.py *.md
        """
    )
    parser.add_argument('files', nargs='+', help='Markdown files to sync')
    parser.add_argument('-p', '--parent', '--parent-id', dest='parent_id',
                        help='Parent page ID (will auto-search if not provided)')

    args = parser.parse_args()

    md_files = args.files
    parent_page_id = args.parent_id

    print(f"Syncing {len(md_files)} files to Notion...")
    if parent_page_id:
        print(f"Parent page ID: {parent_page_id}")
    else:
        print("Parent page: Auto-detect from content")
    print()

    for md_file in md_files:
        if not os.path.exists(md_file):
            print(f"✗ File not found: {md_file}")
            continue

        print(f"Processing: {md_file}")
        try:
            sync_markdown_file(md_file, parent_page_id)
            print()
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            print()


if __name__ == '__main__':
    main()
