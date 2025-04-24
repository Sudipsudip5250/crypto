import subprocess
import os
import time

xmrig_path = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2\xmrig.exe"
working_dir = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2"
log_file = os.path.join(working_dir, "miner_output.log")

os.chdir(working_dir)

while True:
    print("⛏️ Starting miner... Logging to miner_output.log")

    with open(log_file, "a", buffering=1) as log:  # line-buffered
        process = subprocess.Popen(
            [xmrig_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        # Print and log real-time
        for line in process.stdout:
            print(line, end="")
            log.write(line)

    print("❌ Miner crashed or exited. Restarting in 5 seconds...")
    time.sleep(5)
