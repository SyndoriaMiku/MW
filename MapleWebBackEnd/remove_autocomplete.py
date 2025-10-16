#!/usr/bin/env python3
"""
Script to remove all autocomplete_fields lines from admin.py files
"""
import os
import re

# Path to apps directory
apps_dir = 'apps'

# Find all admin.py files
for root, dirs, files in os.walk(apps_dir):
    if 'admin.py' in files:
        admin_file = os.path.join(root, 'admin.py')
        print(f"Processing: {admin_file}")
        
        with open(admin_file, 'r') as f:
            content = f.read()
        
        # Remove autocomplete_fields lines (handles both single and multi-line)
        # Pattern matches: autocomplete_fields = [...] or autocomplete_fields = (...)
        pattern = r'    autocomplete_fields\s*=\s*[\[\(][^\]\)]*[\]\)]\n'
        new_content = re.sub(pattern, '', content)
        
        # Write back
        with open(admin_file, 'w') as f:
            f.write(new_content)
        
        print(f"  ✓ Removed autocomplete_fields")

print("\n✅ Done! All autocomplete_fields removed from admin files.")
