import subprocess
import os

# Full path to XMRig executable
xmrig_path = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2\xmrig.exe"

# Optional: Set working directory to where XMRig and config.json are located
os.chdir(r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2")

# Start the miner (uses config.json automatically)
subprocess.run([xmrig_path])
