"""Write a JSON payload to a file. Used by workflow orchestrators to avoid heredoc prompts.

Usage: python scripts/write_json.py <output_path> <json_string>
"""
import json
import sys

if len(sys.argv) != 3:
    print("Usage: write_json.py <output_path> <json_string>", file=sys.stderr)
    sys.exit(1)

output_path = sys.argv[1]
json_string = sys.argv[2]

data = json.loads(json_string)
with open(output_path, "w") as f:
    json.dump(data, f, indent=2)

print(f"Written: {output_path}")
