#!/home/david/Work/hivematrix/hivematrix-brainhair/pyenv/bin/python
"""
Manage Knowledge Base Articles

Create, update, search, and delete articles in the KnowledgeTree.

IMPORTANT: When creating articles, DO NOT browse or check if paths exist first!
- The 'create' command validates paths automatically and gives clear errors
- If parent doesn't exist, you'll get: "ERROR: Could not find parent path: /path"
- If duplicate name, you'll get: "ERROR: A node with name 'X' already exists"
- Just call 'create' directly - it's fast and handles all validation

To check what exists, use 'browse' AFTER creation to verify, not before.

Usage:
    # Search for articles
    python manage_knowledge.py search <query>
    python manage_knowledge.py search "password reset"

    # Create new article (parent path must exist - tool will verify)
    python manage_knowledge.py create <parent_path> <title> --content "Article content"
    python manage_knowledge.py create "/IT/Windows" "Password Reset Guide" --content "Steps to reset..."
    python manage_knowledge.py create "/Companies/Green Diamond Performance Materials" "overview.md" --content "Company info..."

    # Update existing article (by node ID or path)
    python manage_knowledge.py update <node_id_or_path> --content "Updated content" --title "New Title"
    python manage_knowledge.py update abc-123 --content "New steps..."
    python manage_knowledge.py update "/IT/Windows/Password Reset Guide" --content "Updated steps..."

    # Delete article
    python manage_knowledge.py delete <node_id>
    python manage_knowledge.py delete abc-123

    # Browse structure (shows folders and articles with IDs)
    python manage_knowledge.py browse <path>
    python manage_knowledge.py browse "/IT"
    python manage_knowledge.py browse "/Companies/Green Diamond Performance Materials"

    # Create folder
    python manage_knowledge.py create-folder <parent_path> <folder_name>
    python manage_knowledge.py create-folder "/IT" "Windows"
"""

import sys
import os
import json
import requests
import argparse

# Import approval helper
sys.path.insert(0, os.path.dirname(__file__))
from approval_helper import request_approval

# Service URLs
CORE_URL = os.getenv('CORE_SERVICE_URL', 'http://localhost:5000')
KNOWLEDGETREE_URL = os.getenv('KNOWLEDGETREE_SERVICE_URL', 'http://localhost:5020')


def get_service_token(target_service):
    """Get service token from Core."""
    try:
        response = requests.post(
            f"{CORE_URL}/service-token",
            json={
                "calling_service": "brainhair",
                "target_service": target_service
            },
            timeout=5
        )
        if response.status_code == 200:
            return response.json()["token"]
        return None
    except Exception as e:
        print(f"ERROR: Could not get service token: {e}")
        return None


def search_knowledge(query):
    """Search for knowledge articles."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return []

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{KNOWLEDGETREE_URL}/api/search",
            params={'query': query},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            results = response.json()
            return results
        else:
            print(f"ERROR: Search failed: {response.status_code}")
            return []

    except Exception as e:
        print(f"ERROR: {e}")
        return []


def browse_knowledge(path="/"):
    """Browse knowledge tree at path."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{KNOWLEDGETREE_URL}/api/browse",
            params={'path': path},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR: Browse failed: {response.status_code}")
            return None

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def get_node_id_from_path(path):
    """Get node ID from a path like /IT/Windows."""
    if path == "/" or path == "root":
        return "root"

    # Simply browse to the full path - the API will find it
    browse_result = browse_knowledge(path)
    if not browse_result:
        print(f"ERROR: Could not browse to path: {path}")
        return None

    # Get the current node ID from the browse result
    current_node = browse_result.get('current_node')
    if current_node and current_node.get('id'):
        return current_node['id']

    print(f"ERROR: Path exists but no node ID returned: {path}")
    return None


def create_node(parent_path, name, content="", is_folder=False):
    """Create a new node in the knowledge tree."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Get parent node ID
    parent_id = get_node_id_from_path(parent_path)
    if not parent_id:
        print(f"ERROR: Could not find parent path: {parent_path}")
        return False

    try:
        # Create node
        response = requests.post(
            f"{KNOWLEDGETREE_URL}/api/node",
            json={
                'parent_id': parent_id,
                'name': name,
                'is_folder': is_folder
            },
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            new_id = result.get('id')

            if not new_id:
                print(f"ERROR: Node created but no ID returned")
                return False

            # If not a folder and has content, update it
            if not is_folder and content:
                print(f"Adding content to node {new_id}...")
                update_response = requests.put(
                    f"{KNOWLEDGETREE_URL}/api/node/{new_id}",
                    json={'content': content},
                    headers=headers,
                    timeout=10
                )

                if update_response.status_code != 200:
                    print(f"ERROR: Node created but content update failed: {update_response.status_code}")
                    print(f"Response: {update_response.text}")
                    # Still return the ID so user can manually update
                    print(f"Node ID {new_id} created, but you'll need to add content manually")
                    return new_id
                else:
                    print(f"✓ Content added successfully")

            return new_id
        elif response.status_code == 409:
            # Duplicate name
            result = response.json()
            print(f"ERROR: A node with name '{name}' already exists in {parent_path}")
            print(f"Existing node ID: {result.get('existing_id')}")
            print(f"Use the 'update' command to modify it instead, or delete it first")
            return False
        else:
            print(f"ERROR: Failed to create node: {response.status_code} {response.text}")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def update_node(node_id, title=None, content=None):
    """Update an existing node."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    update_data = {}
    if title:
        update_data['name'] = title
    if content:
        update_data['content'] = content

    if not update_data:
        print("ERROR: No updates specified")
        return False

    try:
        response = requests.put(
            f"{KNOWLEDGETREE_URL}/api/node/{node_id}",
            json=update_data,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return True
        else:
            print(f"ERROR: Failed to update node: {response.status_code} {response.text}")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def delete_node(node_id):
    """Delete a node and its children."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.delete(
            f"{KNOWLEDGETREE_URL}/api/node/{node_id}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return True
        else:
            print(f"ERROR: Failed to delete node: {response.status_code} {response.text}")
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False


def get_node_details(node_id):
    """Get details of a specific node."""
    token = get_service_token("knowledgetree")
    if not token:
        print("ERROR: Could not get service token for KnowledgeTree")
        return None

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{KNOWLEDGETREE_URL}/api/node/{node_id}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            print(f"ERROR: Failed to get node: {response.status_code}")
            return None

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description='Manage Knowledge Base Articles',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for articles')
    search_parser.add_argument('query', help='Search query')

    # Browse command
    browse_parser = subparsers.add_parser('browse', help='Browse knowledge tree')
    browse_parser.add_argument('path', nargs='?', default='/', help='Path to browse')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create new article')
    create_parser.add_argument('parent_path', help='Parent path (e.g., /IT/Windows)')
    create_parser.add_argument('title', help='Article title')
    create_parser.add_argument('--content', default='', help='Article content (markdown)')

    # Create folder command
    folder_parser = subparsers.add_parser('create-folder', help='Create new folder')
    folder_parser.add_argument('parent_path', help='Parent path')
    folder_parser.add_argument('name', help='Folder name')

    # Update command
    update_parser = subparsers.add_parser('update', help='Update existing article')
    update_parser.add_argument('node_id', help='Node ID or full path (e.g., /IT/Windows/article.md)')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--content', help='New content (markdown)')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete article or folder')
    delete_parser.add_argument('node_id', help='Node ID to delete')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == 'search':
        print(f"Searching for: {args.query}")
        results = search_knowledge(args.query)

        if results:
            print(f"\nFound {len(results)} results:\n")
            for result in results:
                folder_type = "📁" if result.get('is_folder') else "📄"
                print(f"{folder_type} {result['name']}")
                print(f"   Path: /{result.get('folder_path', '')}")
                print(f"   ID: {result['id']}")
                print()
        else:
            print("No results found")

    elif args.command == 'browse':
        print(f"Browsing: {args.path}")
        result = browse_knowledge(args.path)

        if result:
            print(f"\nCurrent: {result.get('current_node', {}).get('name', 'root')}")
            print(f"ID: {result.get('current_node', {}).get('id', 'root')}")
            print("\nChildren:")

            # Show folders (categories)
            for category in result.get('categories', []):
                print(f"  📁 {category['name']}")

            # Show articles
            for article in result.get('articles', []):
                print(f"  📄 {article['title']} (ID: {article['id']})")
        else:
            print("Path not found")

    elif args.command == 'create':
        # Request approval
        approved = request_approval(
            f"Create knowledge article: {args.title}",
            {
                'Parent Path': args.parent_path,
                'Title': args.title,
                'Content Length': f"{len(args.content)} characters",
                'Action': 'Create new article in KnowledgeTree'
            }
        )

        if not approved:
            print("✗ User denied the change")
            sys.exit(1)

        print(f"Creating article: {args.title} in {args.parent_path}")
        node_id = create_node(args.parent_path, args.title, args.content, is_folder=False)

        if node_id:
            print(f"✓ Article created successfully")
            print(f"  ID: {node_id}")
            print(f"  Path: {args.parent_path}/{args.title}")
        else:
            print("✗ Failed to create article")
            sys.exit(1)

    elif args.command == 'create-folder':
        # Request approval
        approved = request_approval(
            f"Create knowledge folder: {args.name}",
            {
                'Parent Path': args.parent_path,
                'Folder Name': args.name,
                'Action': 'Create new folder in KnowledgeTree'
            }
        )

        if not approved:
            print("✗ User denied the change")
            sys.exit(1)

        print(f"Creating folder: {args.name} in {args.parent_path}")
        node_id = create_node(args.parent_path, args.name, is_folder=True)

        if node_id:
            print(f"✓ Folder created successfully")
            print(f"  ID: {node_id}")
            print(f"  Path: {args.parent_path}/{args.name}")
        else:
            print("✗ Failed to create folder")
            sys.exit(1)

    elif args.command == 'update':
        # Check if node_id is a path or an ID
        node_id = args.node_id
        if node_id.startswith('/'):
            # It's a path, convert to node ID
            print(f"Resolving path: {node_id}")
            node_id = get_node_id_from_path(node_id)
            if not node_id:
                print(f"ERROR: Could not find node at path: {args.node_id}")
                sys.exit(1)
            print(f"Found node ID: {node_id}")

        # Get current node details for approval
        node = get_node_details(node_id)
        if not node:
            print(f"ERROR: Node not found: {node_id}")
            sys.exit(1)

        # Request approval
        approval_details = {
            'Current Title': node.get('name', 'Unknown'),
            'Node ID': node_id,
            'Action': 'Update article in KnowledgeTree'
        }

        if args.title:
            approval_details['New Title'] = args.title
        if args.content:
            approval_details['Content Update'] = f"{len(args.content)} characters"

        approved = request_approval(
            f"Update knowledge article: {node.get('name')}",
            approval_details
        )

        if not approved:
            print("✗ User denied the change")
            sys.exit(1)

        print(f"Updating node: {node_id}")
        if update_node(node_id, title=args.title, content=args.content):
            print(f"✓ Article updated successfully")
        else:
            print("✗ Failed to update article")
            sys.exit(1)

    elif args.command == 'delete':
        # Get node details for approval
        node = get_node_details(args.node_id)
        if not node:
            print(f"ERROR: Node not found: {args.node_id}")
            sys.exit(1)

        # Request approval
        approved = request_approval(
            f"Delete knowledge article: {node.get('name')}",
            {
                'Title': node.get('name', 'Unknown'),
                'Node ID': args.node_id,
                'Type': 'Folder' if node.get('is_folder') else 'Article',
                'Action': 'Delete from KnowledgeTree (includes children if folder)'
            }
        )

        if not approved:
            print("✗ User denied the change")
            sys.exit(1)

        print(f"Deleting node: {args.node_id}")
        if delete_node(args.node_id):
            print(f"✓ Article deleted successfully")
        else:
            print("✗ Failed to delete article")
            sys.exit(1)


if __name__ == "__main__":
    main()
