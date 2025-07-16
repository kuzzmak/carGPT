import shutil
import tempfile
import time
from stem.process import launch_tor_with_config

def start_tor_instances(count=3, base_port=9050):
    base_control_port = 9051
    tor_instances = []

    for i in range(count):
        socks_port = base_port + i * 10
        control_port = base_control_port + i * 10
        data_dir = tempfile.mkdtemp(prefix=f'tor_data_{i}_')

        print(f"Starting Tor instance {i}:")
        print(f"  SOCKS Port: {socks_port}")
        print(f"  Control Port: {control_port}")
        print(f"  Data Directory: {data_dir}")

        try:
            tor = launch_tor_with_config(
                config={
                    'SocksPort': str(socks_port),
                    'ControlPort': str(control_port),
                    'DataDirectory': data_dir,
                },
                init_msg_handler=lambda line: print(f"[tor{i}] {line}"),
                take_ownership=True,
                tor_cmd=r"...",
            )
            tor_instances.append({
                'process': tor,
                'socks_port': socks_port,
                'control_port': control_port,
                'data_dir': data_dir
            })
        except Exception as e:
            print(f"Failed to launch Tor instance {i}: {e}")
            shutil.rmtree(data_dir)

    return tor_instances

def stop_tor_instances(tor_instances):
    for inst in tor_instances:
        print(f"Stopping Tor on port {inst['socks_port']}")
        inst['process'].terminate()
        shutil.rmtree(inst['data_dir'], ignore_errors=True)

# Example usage
if __name__ == '__main__':
    instances = start_tor_instances(count=2)
    try:
        print("Tor instances are running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping all Tor instances...")
        stop_tor_instances(instances)
