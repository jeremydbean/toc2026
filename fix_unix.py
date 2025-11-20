import sys
path = 'src/merc.h'
with open(path, 'r') as f:
    content = f.read()

old_block = '#if !defined(unix) && (defined(__unix__) || defined(__unix) || defined(__linux__))'
new_block = '#if !defined(unix) && (defined(__unix__) || defined(__unix) || defined(__linux__) || defined(__APPLE__))'

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(path, 'w') as f:
        f.write(content)
    print('Updated unix definition in src/merc.h')
else:
    print('Could not find unix definition block in src/merc.h')
