import struct, os

files = [
    'patched_run/bridge/VolumetricaBridge.exe.bak-rithmic-dataonly-20260514-173941',
    'patched_run/bridge/VolumetricaBridge.exe.bak-rithmic-skip-trade-setup-20260514-174304',
    'patched_run/bridge/VolumetricaBridge.exe.bak-skip-rithmic-repository-20260515-135414',
    'patched_run/bridge/VolumetricaBridge.exe',
]

keywords = ['rithmic.com', 'wss://', 'paper.', 'aurora.', 'conformance', 'api.rithmic', 'gateway', '55555', '44444', '40000', '56000', '63100', '64100', '65000']

for f in files:
    fname = os.path.basename(f)
    try:
        with open(f, 'rb') as fh:
            data = fh.read()
        strings = set()
        current = b''
        for byte in data:
            if 32 <= byte <= 126:
                current += bytes([byte])
            else:
                if len(current) >= 6:
                    s = current.decode('ascii', errors='replace').strip()
                    for kw in keywords:
                        if kw in s.lower():
                            strings.add(s)
                current = b''
        if strings:
            print('=== {} ==='.format(fname))
            for s in sorted(strings):
                print('  {}'.format(s))
        else:
            print('=== {} === (no matches)'.format(fname))
    except Exception as e:
        print('{}: {}'.format(fname, e))
