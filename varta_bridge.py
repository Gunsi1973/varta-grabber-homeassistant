import time
import json
import logging
import argparse
import sys
import re
import requests
import paho.mqtt.client as mqtt

# --- Configuration ---
DEFAULT_VARTA_IP = "192.168.1.58" 
DEFAULT_INTERVAL = 5 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class VartaBridge:
    def __init__(self, ip, mqtt_broker, mqtt_port, dry_run=False):
        self.url = f"http://{ip}/cgi/ems_data.js"
        self.dry_run = dry_run
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = "energy/varta/status"
        
        if not self.dry_run:
            self.client = mqtt.Client()
            try:
                self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
                self.client.loop_start()
            except Exception as e:
                logger.error(f"MQTT Connection Failed: {e}")
                sys.exit(1)

    def fetch_data(self):
        try:
            response = requests.get(self.url, timeout=5)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Fetch Error: {e}")
            return None

    def parse_and_scan(self, js_content):
        # Extract WR_Data array
        match = re.search(r"WR_Data\s*=\s*\[(.*?)\];", js_content, re.DOTALL)
        if not match: return None

        raw_values = match.group(1).replace('"', '').replace('\n', '').split(',')
        data = []
        for v in raw_values:
            try:
                data.append(int(v))
            except ValueError:
                data.append(0)

        # --- THE SCANNER ---
        # This prints a map of ALL active values to find your '650W'
        if self.dry_run:
            print("\n--- DATA MAPPING (Compare these to your Web UI) ---")
            print(f"Index 16 (Battery?): {data[16] if len(data)>16 else 'N/A'}")
            print(f"Index 21 (Grid?):    {data[21] if len(data)>21 else 'N/A'}")
            
            # Print any value that looks like a power reading (> 10 Watts)
            print("Potentially interesting values:")
            for i, val in enumerate(data):
                # Filter out obvious voltages (around 230) and 0s
                if abs(val) > 10 and not (210 < abs(val) < 250):
                    print(f"  Index [{i}]: {val}")
            print("---------------------------------------------------")

        # --- PRODUCTION MAPPING (Update this after you confirm indices) ---
        # Based on your logs, I strongly suspect:
        # Index 16 = Battery (Positive = Discharge, Negative = Charge)
        # Index 21 = Grid (Positive = Import, Negative = Export)
        # Index 29 = House Consumption ?? (Needs verification)
        
        payload = {
            "timestamp": time.time(),
            "soc": 0, # We can add parsing for SOC later if needed
            "battery_power": data[16] if len(data) > 16 else 0,
            "grid_power": data[21] if len(data) > 21 else 0,
            "potential_house_load": data[29] if len(data) > 29 else 0, # TESTING THIS
        }
        
        # Calculate HA Energy Dashboard friendly values
        bat = payload["battery_power"]
        payload["bat_charge"] = abs(bat) if bat < 0 else 0
        payload["bat_discharge"] = bat if bat > 0 else 0
        
        grid = payload["grid_power"]
        payload["grid_import"] = grid if grid > 0 else 0
        payload["grid_export"] = abs(grid) if grid < 0 else 0

        return payload

    def run(self, interval):
        while True:
            js_data = self.fetch_data()
            if js_data:
                payload = self.parse_and_scan(js_data)
                if not self.dry_run and payload:
                    self.client.publish(self.mqtt_topic, json.dumps(payload))
                    logger.info(f"Sent MQTT: Grid {payload['grid_power']}W | Bat {payload['battery_power']}W")
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--ip', type=str, default=DEFAULT_VARTA_IP)
    parser.add_argument('--mqtt-host', type=str, default="localhost")
    args = parser.parse_args()

    bridge = VartaBridge(args.ip, args.mqtt_host, 1883, args.dry_run)
    bridge.run(DEFAULT_INTERVAL)