"""Clear the ATS platform search cache directory before a new run."""
import glob
import os

cache_dir = "results/ats_platform_cache"
os.makedirs(cache_dir, exist_ok=True)

removed = 0
for f in glob.glob(os.path.join(cache_dir, "*.json")):
    os.remove(f)
    removed += 1

print(f"Cache cleared: removed {removed} file(s) from {cache_dir}")
