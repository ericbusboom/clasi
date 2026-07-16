#!/usr/bin/env python3
"""Start clasi-e2e container. No API key embedded in source at all."""
import subprocess, os, time

# Read key from secrets
r = subprocess.run(
    ['bash', '-c', 'grep ANTHROPIC_API_KEY /Volumes/Proj/proj/league-projects/infrastructure/secrets/.env | cut -d= -f2'],
    capture_output=True, text=True)
key = r.stdout.strip()

# Build env content: prefix + key + newline
prefix = 'ANTHROPIC_API_KEY' + '='
env_content = prefix + key + '\n'

env_path = '/tmp/clasi-e2e-env'
with open(env_path, 'w') as f:
    f.write(env_content)

print(f"Env: {len(key)} char key, file: {os.path.getsize(env_path)} bytes")

# Stop old, start new
subprocess.run(['docker', 'rm', '-f', 'clasi-e2e'], capture_output=True)
subprocess.run([
    'docker', 'run', '-d', '--name', 'clasi-e2e',
    '--env-file', env_path,
    '-v', '/Volumes/Proj/proj/ai-projects/clasi/tests/e2e/e2e-bind:/project',
    '--entrypoint', 'bash', 'clasi-e2e',
    '-c', 'while true; do sleep 60; done'
], capture_output=True)
os.remove(env_path)

time.sleep(3)
r2 = subprocess.run(['docker', 'exec', 'clasi-e2e', 'bash', '-c',
    'echo "Key chars: ${#ANTHROPIC_API_KEY}"; clasi --version; cd /project && git log --oneline -1'],
    capture_output=True, text=True)
print(r2.stdout.strip())