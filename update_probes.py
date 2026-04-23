import json
import os
from stlink_toolkit import Registry, find_probes

# Initialize Registry with a local file
registry_path = './probes.json'
registry = Registry(registry_path)

# Find live probes
detected_probes = find_probes()

probes_dict = {}
for p in detected_probes:
    serial = p.serial
    nick = serial[-3:] if serial else "unknown"
    model = getattr(p, 'model', 'unknown')
    probes_dict[serial] = {
        'nick': nick,
        'model': model
    }

# Construct the registry object
data = {
    'probes': probes_dict,
    'boards': {},
    'mode_probe_map': {},
    'mode_probe_map_auto_update': False
}

# Write to probes.json
with open(registry_path, 'w') as f:
    json.dump(data, f, indent=4)

print(f"File {registry_path} created/updated.")
