import os

filepath = r"c:\whodados\analise-empresarial-streamlit\whodados\frontend\src\app\dashboard\crm\page.tsx"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Remove lines 218-335 (the broken duplicate code)
# Keep lines 1-217, then jump to line 336 onwards
fixed_content = lines[:217]  # lines 1-217 (index 0-216)
fixed_content.extend(lines[335:])  # skip lines 218-335, keep from line 336

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(fixed_content)

print("File fixed - removed broken duplicate code")
print(f"Original lines: {len(lines)}")
print(f"Fixed lines: {len(fixed_content)}")