import struct, os

files = [
    'patched_run/bridge/VolumetricaBridge.exe.bak-rithmic-dataonly-20260514-173941',
    'patched_run/bridge/VolumetricaBridge.exe.bak-rithmic-skip-trade-setup-20260514-174304',
    'patched_run/bridge/VolumetricaBridge.exe.bak-skip-rithmic-repository-20260515-135414',
    'patched_run/bridge/VolumetricaBridge.exe',
]

# Look for enum values and server names
for f in files:
    fname = os.path.basename(f)
    try:
        with open(f, 'rb') as fh:
            data = fh.read()
        # Extract all printable strings >= 4 chars
        strings = set()
        current = b''
        for byte in data:
            if 32 <= byte <= 126:
                current += bytes([byte])
            else:
                if len(current) >= 4:
                    s = current.decode('ascii', errors='replace').strip()
                    strings.add(s)
                current = b''
        
        # Look for server-related values
        relevant = set()
        for s in sorted(strings):
            sl = s.lower()
            # Gateway names, server names, URL-like strings
            if any(kw in sl for kw in ['gateway', 'server', 'rithmic', 'wss://', 'connect', '_plant', 'ticker', 'order_history', 'pnl']):
                if any(c.isalpha() for c in s):
                    relevant.add(s)
        
        if relevant:
            print('=== {} ==='.format(fname))
            for s in sorted(relevant, key=lambda x: x.lower()):
                print('  {}'.format(s))
    except Exception as e:
        print('{}: {}'.format(fname, e))
