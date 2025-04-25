import subprocess
import os
import time
import threading
import keyboard  # pip install keyboard
import psutil    # pip install psutil

# Paths
xmrig_path = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2\xmrig.exe"
working_dir = r"C:\Users\hp\Desktop\crypto\xmrig-6.22.2"
coretemp_txt = r"C:\Program Files\Core Temp\coretemp.txt"
log_file = os.path.join(working_dir, "miner_log.txt")
os.chdir(working_dir)

# Settings
run_duration = 15 * 60  # 15 minutes
rest_duration = 5 * 60  # 5 minutes
max_temp = 70
min_temp = 55
max_threads = 3  # You can adjust this to your CPU's limit
cool_core = 1    # Pin threads to Core #1 (CPU index 1)

# Quit flag
should_quit = False

def listen_for_quit():
    global should_quit
    while True:
        if keyboard.is_pressed("q"):
            print("❌ Quit signal received (Q). Will exit after this cycle.")
            should_quit = True
            break

# Start the quit key listener
threading.Thread(target=listen_for_quit, daemon=True).start()

def get_cpu_temp():
    try:
        with open(coretemp_txt, 'r') as f:
            for line in f:
                if "CPU Temperature" in line:
                    return int(line.strip().split()[-1].replace("°C", ""))
    except:
        return None

cycle = 1
while True:
    temp = get_cpu_temp()
    thread_count = 0  # Default: no mining

    if temp:
        if temp < min_temp:
            thread_count = max_threads
        elif temp < max_temp:
            thread_count = max_threads - 1
        elif temp >= max_temp:
            print(f"🔥 CPU temp {temp}°C too high — skipping this cycle to cool down.")
            with open(log_file, "a") as log:
                log.write(f"[CYCLE {cycle}] Skipped due to high temp ({temp}°C)\n")
            time.sleep(rest_duration)
            if should_quit:
                print("✅ Quit flag detected. Exiting cleanly.")
                break
            cycle += 1
            continue

    print(f"🔁 Cycle {cycle}: Starting miner with {thread_count} threads...")
    with open(log_file, "a") as log:
        log.write(f"\n[CYCLE {cycle}] Started at {time.ctime()} | Threads: {thread_count}\n")

    # Launch XMRig with thread count
    miner = subprocess.Popen([xmrig_path, f"--threads={thread_count}"])
    time.sleep(2)

    # Apply CPU affinity: pin to Core #1 (CPU index 1)
    try:
        proc = psutil.Process(miner.pid)
        proc.cpu_affinity([cool_core])
        print(f"✅ Miner pinned to Core #{cool_core}")
    except Exception as e:
        print("⚠️ Failed to set CPU affinity:", e)

    start_time = time.time()
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
