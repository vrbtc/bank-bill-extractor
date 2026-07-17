"""Replace leaked API_KEY in all files during git filter-branch."""
import os
import sys

LEAKED_KEY = "dp_5dd5bf5607374d03bf0856775b94592f"
REPLACEMENT = "REDACTED_API_KEY"

for root, dirs, files in os.walk('.'):
    # Skip .git directory
    if '.git' in dirs:
        dirs.remove('.git')
    
    for fname in files:
        fpath = os.path.join(root, fname)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if LEAKED_KEY in content:
                new_content = content.replace(LEAKED_KEY, REPLACEMENT)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"  Cleaned: {fpath}")
        except Exception:
            pass
