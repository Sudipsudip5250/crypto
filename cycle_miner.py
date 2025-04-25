import subprocess
import os
import time

xmrig_path = r"./xmrig-6.22.2/xmrig.exe"
working_dir = r"./xmrig-6.22.2"
coretemp_txt = r"C:/Program Files/Core Temp/coretemp.txt"
log_file = os.path.join(working_dir, "miner_log.txt")

os.chdir(working_dir)

run_duration = 15 * 60  # 15 min
rest_duration = 5 * 60  # 5 min
max_temp = 70           # °C - stop if exceeds this

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
    print(f"🔁 Cycle {cycle}: Starting miner for 15 minutes...")
    with open(log_file, "a") as log:
        log.write(f"\n[CYCLE {cycle}] Mining started at {time.ctime()}\n")
    
    miner = subprocess.Popen([xmrig_path])
    start_time = time.time()

    while time.time() - start_time < run_duration:
        temp = get_cpu_temp()
        if temp:
            print(f"🌡️ CPU Temp: {temp}°C")
            with open(log_file, "a") as log:
                log.write(f"[{time.ctime()}] Temp: {temp}°C\n")
            if temp >= max_temp:
                print("🚨 Temp too high! Stopping miner...")
                miner.terminate()
                miner.wait()
                break
        time.sleep(60)  # check temp every 60 seconds

    if miner.poll() is None:  # still running? Stop it.
        print("🛑 Stopping miner after full cycle...")
        miner.terminate()
        miner.wait()

    with open(log_file, "a") as log:
        log.write(f"[CYCLE {cycle}] Miner stopped at {time.ctime()}\n")

    print("😴 Cooling down for 5 minutes...\n")
    time.sleep(rest_duration)
    cycle += 1
