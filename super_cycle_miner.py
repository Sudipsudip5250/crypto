import subprocess
import os
import time
import threading
import keyboard  # pip install keyboard

# Paths
xmrig_path = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2\xmrig.exe"
working_dir = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2"
coretemp_txt = r"C:\Program Files\Core Temp\coretemp.txt"
log_file = os.path.join(working_dir, "miner_log.txt")
os.chdir(working_dir)

# Settings
run_duration = 15 * 60  # 15 min
rest_duration = 5 * 60  # 5 min
max_temp = 70           # Temp limit
min_temp = 55
max_threads = 3         # Your max CPU threads (i5-2410M has 4 threads)

# Global Quit Flag
should_quit = False

# Thread listener for 'Q' key quit
def listen_for_quit():
    global should_quit
    while True:
        if keyboard.is_pressed("q"):
            print("❌ Quit signal received (Q). Will exit after this cycle.")
            should_quit = True
            break

# Get CPU temp from CoreTemp export
def get_cpu_temp():
    try:
        with open(coretemp_txt, 'r') as f:
            for line in f:
                if "CPU Temperature" in line:
                    return int(line.strip().split()[-1].replace("°C", ""))
    except:
        return None

# Start listener thread
threading.Thread(target=listen_for_quit, daemon=True).start()

cycle = 1
while True:
    temp = get_cpu_temp()
    thread_count = 1
    if temp:
        if temp < min_temp:
            thread_count = max_threads
        elif temp < max_temp:
            thread_count = max_threads - 1
        else:
            thread_count = 1

    print(f"🔁 Cycle {cycle}: Starting miner with {thread_count} threads...")
    with open(log_file, "a") as log:
        log.write(f"\n[CYCLE {cycle}] Started at {time.ctime()} | Threads: {thread_count}\n")

    # Start XMRig with thread config
    miner = subprocess.Popen([xmrig_path, f"--threads={thread_count}"])
    start_time = time.time()

    # Monitor temp during mining cycle
    while time.time() - start_time < run_duration:
        temp = get_cpu_temp()
        if temp:
            print(f"🌡️ CPU Temp: {temp}°C")
            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] Temp: {temp}°C\n")
            if temp >= max_temp:
                print("🚨 Overheat! Stopping miner early.")
                miner.terminate()
                miner.wait()
                break
        time.sleep(60)

    # Graceful stop
    if miner.poll() is None:
        print("🛑 Stopping miner after full cycle...")
        miner.terminate()
        miner.wait()

    with open(log_file, "a") as log:
        log.write(f"[CYCLE {cycle}] Ended at {time.ctime()}\n")

    print("😴 Cooling down for 5 minutes...\n")
    time.sleep(rest_duration)

    if should_quit:
        print("✅ Quit flag detected. Exiting cleanly.")
        break

    cycle += 1
