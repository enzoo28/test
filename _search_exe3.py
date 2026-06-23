import struct, os

files = [
    'patched_run/bridge/VolumetricaBridge.exe.bak-rithmic-dataonly-20260514-173941',
    'patched_run/bridge/VolumetricaBridge.exe',
]

# Look for IP addresses and DNS names near Rithmic gateway names
for f in files:
    fname = os.path.basename(f)
    try:
        with open(f, 'rb') as fh:
            data = fh.read()
        
        # Extract all printable strings >= 4 chars with positions
        strings = []
        i = 0
        while i < len(data):
            if 32 <= data[i] <= 126:
                start = i
                while i < len(data) and 32 <= data[i] <= 126:
                    i += 1
                s = data[start:i].decode('ascii', errors='replace').strip()
                if len(s) >= 4:
                    strings.append((start, s))
            else:
                i += 1
        
        # Look for strings that look like IPs or hostnames
        import re
        print('=== {} ==='.format(fname))
        
        # Find all IP-like strings
        for pos, s in strings:
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', s):
                # Check context (strings near this position)
                nearby = []
                for p2, s2 in strings:
                    if abs(p2 - pos) < 200 and s2 != s:
                        nearby.append(s2)
                print('  IP: {} at pos {}'.format(s, pos))
                print('    Nearby: {}'.format(nearby[:10]))
                
        # Find hostnames like *.rithmic.com
        for pos, s in strings:
            if 'rithmic' in s.lower() and ('.' in s or s.startswith('Rithmic')):
                pass  # Already seen these
                
    except Exception as e:
        print('{}: {}'.format(fname, e))
