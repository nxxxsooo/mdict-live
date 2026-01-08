import os
import sys
import shutil
import re

import re

try:
    from readmdict import MDX
except ImportError as e:
    print(f"Error importing MDX: {e}")
    print("Please make sure 'flask-mdict' is present in the parent directory.")
    sys.exit(1)

TITLE_MAPPING = {
    '林语堂当代汉英词典-繁简索引': 'Lin_Yutang_Chinese_English_Dictionary',
    '牛津高阶英汉双解词典（第10版）V3': 'Oxford_Advanced_Learners_Dictionary_10th',
    '现代英汉汉英综合大辞典': 'Modern_Comprehensive_English_Chinese_Dictionary',
    '韦氏高阶英汉双解词典': 'Merriam_Webster_Advanced_Learners_Dictionary',
    'The 21st Century Unabridged English-Chinese Dictionary': 'The_21st_Century_Unabridged_English_Chinese_Dictionary',
}

# Fallback for files where metadata reading fails (e.g. LZO compression)
FILENAME_MAPPING = {
    '中華成語大詞典[49450](090316).mdx': 'Chinese_Idiom_Dictionary',
    '现代汉语词典.mdx': 'Modern_Chinese_Dictionary',
}

# Explicit folder renames
FOLDER_MAPPING = {
    '汉语字词典': 'Chinese_Dictionaries',
}

def sanitize_name_english(name):
    # Replace spaces and hyphens with underscores
    name = re.sub(r'[ \-]', '_', name)
    # Remove any other non-alphanumeric chars (except underscores)
    name = re.sub(r'[^\w_]', '', name)
    # Collapse multiple underscores
    name = re.sub(r'_+', '_', name)
    return name.strip('_')

def organize_dictionaries(base_dir):
    print(f"Scanning directory: {base_dir}")
    if not os.path.exists(base_dir):
        print(f"Directory not found: {base_dir}")
        return

    # Walk top-down
    for root, dirs, files in os.walk(base_dir):
        # We only process if there is an mdx file
        mdx_files = [f for f in files if f.lower().endswith('.mdx')]
        
        for filename in mdx_files:
            mdx_path = os.path.join(root, filename)
            title = None
            new_basename = None

            # 1. Try Filename Mapping first (for known failed files)
            if filename in FILENAME_MAPPING:
                new_basename = FILENAME_MAPPING[filename]
                title = "Unknown (LZO)"
            else:
                # 2. Try Reading Metadata
                try:
                    mdx = MDX(mdx_path, encoding='', substyle=False, passcode=None)
                    title = mdx.header.get(b'Title', b'').decode('utf-8', errors='ignore').strip()
                except Exception as e:
                    print(f"Error reading metadata from {filename}: {e}")
                    # Move to _unsupported
                    unsupported_dir = os.path.join(base_dir, '_unsupported')
                    os.makedirs(unsupported_dir, exist_ok=True)
                    
                    print(f"Moving unsupported/error file {filename} to {unsupported_dir}")
                    
                    # Move the MDX file
                    try:
                        shutil.move(mdx_path, os.path.join(unsupported_dir, filename))
                    except Exception as move_error:
                         print(f"Error moving {filename}: {move_error}")

                    # Move related files
                    base_origin = os.path.splitext(filename)[0]
                    for f in os.listdir(root):
                        if f == filename: continue
                        if f.startswith(base_origin):
                             suffix = f[len(base_origin):]
                             if suffix.startswith('.') or suffix == '':
                                 old_file = os.path.join(root, f)
                                 # Checking if it still exists (it might have been moved if we are not careful, but loop should be safe)
                                 if os.path.exists(old_file):
                                     print(f"  Moving Related: '{f}'")
                                     try:
                                        shutil.move(old_file, os.path.join(unsupported_dir, f))
                                     except Exception as move_error:
                                        print(f"Error moving related file {f}: {move_error}")
                    continue

                if not title:
                    print(f"Skipping {filename}: No Title found in metadata.")
                    continue

                # Determine new base name
                if title in TITLE_MAPPING:
                    new_basename = TITLE_MAPPING[title]
                else:
                    new_basename = sanitize_name_english(title)
            
            if not new_basename:
                print(f"Skipping {filename}: Sanitized title is empty (Original: {title})")
                continue

            # Rename MDX
            new_mdx_name = new_basename + '.mdx'
            new_mdx_path = os.path.join(root, new_mdx_name)
            
            if mdx_path != new_mdx_path:
                print(f"Processing '{filename}' (Title: {title}) -> '{new_basename}'")
                print(f"  Renaming File: '{filename}' -> '{new_mdx_name}'")
                os.rename(mdx_path, new_mdx_path)
            
            # Rename companion files
            base_origin = os.path.splitext(filename)[0]
            for f in os.listdir(root):
                if f == filename: continue
                if f == new_mdx_name: continue 

                # STRICT MATCH: file must start with original base name
                if f.startswith(base_origin):
                    suffix = f[len(base_origin):]
                    if suffix.startswith('.') or suffix == '':
                         new_name = new_basename + suffix
                         old_file = os.path.join(root, f)
                         new_file = os.path.join(root, new_name)
                         if old_file != new_file:
                             print(f"  Renaming Related: '{f}' -> '{new_name}'")
                             os.rename(old_file, new_file)

        # Rename Parent Folder (Explicit Mapping)
        parent_dir = os.path.basename(root)
        if parent_dir in FOLDER_MAPPING:
            new_parent_name = FOLDER_MAPPING[parent_dir]
            if parent_dir != new_parent_name:
                new_root = os.path.join(os.path.dirname(root), new_parent_name)
                print(f"  Renaming Folder: '{parent_dir}' -> '{new_parent_name}'")
                try:
                    os.rename(root, new_root)
                except Exception as e:
                     print(f"Error renaming folder {parent_dir}: {e}")
        
        # Rename Parent Folder (Implicit - Single Dictionary)
        # Only rename if NOT already handled by explicit mapping
        elif parent_dir not in FOLDER_MAPPING:
             # Check if we should rename folder based on single dictionary logic...
             # The existing logic was to check if folder name matches new_basename
             # But we might have multiple files. 
             # If multiple files exist, we SKIP unless explicit map.
             if len(mdx_files) == 1:
                # Get the new basename of that single file. we need to re-derive or remember it.
                # Since we iterated above, let's find the current name of the mdx file in directory
                current_mdx = [f for f in os.listdir(root) if f.lower().endswith('.mdx')]
                if len(current_mdx) == 1:
                     current_base = os.path.splitext(current_mdx[0])[0]
                     if parent_dir != current_base:
                         new_root = os.path.join(os.path.dirname(root), current_base)
                         if root != new_root:
                             print(f"  Renaming Folder (Single Dict): '{parent_dir}' -> '{current_base}'")
                             try:
                                os.rename(root, new_root)
                             except Exception as e:
                                print(f"Error renaming folder {parent_dir}: {e}")

if __name__ == "__main__":
    # Default to content/source
    content_dir = os.path.join(os.path.dirname(__file__), '../content/source')
    if len(sys.argv) > 1:
        content_dir = sys.argv[1]
    
    organize_dictionaries(content_dir)
