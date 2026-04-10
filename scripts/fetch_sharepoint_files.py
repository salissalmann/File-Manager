#!/usr/bin/env python3
"""Fetch filenames and URLs from a SharePoint folder using the REST API."""

import csv
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    from office365.runtime.auth.client_credential import ClientCredential
    from office365.sharepoint.client_context import ClientContext
except ImportError:
    print("Error: Missing dependencies. Run 'make install' to install office365-rest-python-client and python-dotenv.")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

def get_sharepoint_context():
    """Authenticate and return SharePoint ClientContext."""
    site_url = os.getenv("SHAREPOINT_SITE_URL")
    client_id = os.getenv("SHAREPOINT_CLIENT_ID")
    client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")

    if not all([site_url, client_id, client_secret]):
        print("Error: Missing SharePoint credentials in .env file.")
        print("Required: SHAREPOINT_SITE_URL, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET")
        sys.exit(1)

    try:
        credentials = ClientCredential(client_id, client_secret)
        ctx = ClientContext(site_url).with_credentials(credentials)
        return ctx
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

def fetch_files():
    """Fetch files from the configured SharePoint folder."""
    ctx = get_sharepoint_context()
    folder_path = os.getenv("SHAREPOINT_FOLDER_PATH", "Shared Documents")
    
    print(f"Connecting to SharePoint site: {os.getenv('SHAREPOINT_SITE_URL')}")
    print(f"Accessing folder: {folder_path}...")

    try:
        target_folder = ctx.web.get_folder_by_server_relative_url(folder_path)
        files = target_folder.files
        ctx.load(files)
        ctx.execute_query()
    except Exception as e:
        print(f"Failed to access folder or fetch files: {e}")
        sys.exit(1)

    print(f"Found {len(files)} files.")

    # Prepare data
    file_data = []
    filenames_only = []
    
    site_url = os.getenv("SHAREPOINT_SITE_URL").rstrip("/")
    
    for i, file in enumerate(files, start=1):
        name = file.name
        # Build the full SharePoint URL
        # file.serverRelativeUrl usually starts with /
        relative_url = file.server_relative_url
        full_url = f"{site_url}{relative_url}"
        
        file_data.append({
            "Index": i,
            "File Name": name,
            "SharePoint Path": full_url
        })
        filenames_only.append(name)

    # Write to CSV
    output_csv = Path("outputs/sharepoint_files.csv")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Index", "File Name", "SharePoint Path"])
        writer.writeheader()
        writer.writerows(file_data)
    
    print(f"Created CSV: {output_csv.resolve()}")

    # Update input/filenames.txt for the matching engine
    input_txt = Path("inputs/filenames.txt")
    input_txt.parent.mkdir(parents=True, exist_ok=True)
    
    with open(input_txt, "w", encoding="utf-8") as f:
        for name in filenames_only:
            f.write(f"{name}\n")
    
    print(f"Updated: {input_txt.resolve()} (Ready for matching engine)")

if __name__ == "__main__":
    fetch_files()
