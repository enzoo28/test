import struct, os, re

# Search rapiplus.dll for Rithmic server-related strings
files = ['patched_run/bridge/rapiplus.dll', 'patched_run/bridge/ETISStdRec.dll']

for f in files:
    fname = os.path.basename(f)
    if not os.path.exists(f):
        print('{}: not found'.format(fname))
        continue
    try:
        with open(f, 'rb') as fh:
            data = fh.read()
        
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
        
        print('=== {} ({} strings) ==='.format(fname, len(strings)))
        
        # Find IP addresses
        ip_count = 0
        for pos, s in strings:
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', s):
                octets = s.split('.')
                if all(0 <= int(o) <= 255 for o in octets):
                    if int(octets[0]) not in [0, 10, 127, 169, 224, 240, 248, 252, 255]:
                        # Not a private/reserved IP
                        print('  IP: {} at pos {}'.format(s, pos))
                        ip_count += 1
        
        if ip_count == 0:
            print('  (no public IPs found)')
            
        # Find DNS-like hostnames
        dns_count = 0
        for pos, s in strings:
            if re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$', s):
                if 'example' not in s.lower() and 'domain' not in s.lower():
                    print('  DNS: {} at pos {}'.format(s, pos))
                    dns_count += 1
        if dns_count == 0:
            print('  (no DNS hostnames found)')
            
    except Exception as e:
        print('{}: {}'.format(fname, e))
