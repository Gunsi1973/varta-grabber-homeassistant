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
    def __init__(self, ip, mqtt_broker, mqtt_port, mqtt_user, mqtt_password, dry_run=False):
        self.base_url = f"http://{ip}/cgi/ems_data.js"
        self.dry_run = dry_run
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = "energy/varta/status"
        
        # Headers to look like a real browser (prevents some server blocks)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f'http://{ip}/home.html'
        }

        if not self.dry_run:
            self.client = mqtt.Client()
            if mqtt_user and mqtt_password:
                self.client.username_pw_set(mqtt_user, mqtt_password)
            try:
                self.client.connect(self.mqtt_broker, self.mqtt_port, 60)
                self.client.loop_start()
                logger.info(f"Connected to MQTT Broker: {self.mqtt_broker}")
            except Exception as e:
                logger.error(f"Failed to connect to MQTT: {e}")
                sys.exit(1)

    def fetch_data(self):
        try:
            # CACHE BUSTER: Add current time parameter to force new data
            params = {'_': int(time.time() * 1000)} 
            
            response = requests.get(self.base_url, headers=self.headers, params=params, timeout=5)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Fetch Error: {e}")
            return None

    def parse_data(self, js_content):
        try:
            # 1. Extract WR_Data array
            match_wr = re.search(r"WR_Data\s*=\s*\[(.*?)\];", js_content, re.DOTALL)
            if not match_wr: return None

            # Convert to list of numbers
            raw_wr = match_wr.group(1).replace('"', '').replace('\n', '').split(',')
            data = []
            for v in raw_wr:
                try:
                    data.append(int(v))
                except ValueError:
                    data.append(0)

            # 2. Extract SOC from Charger_Data
            # Charger_Data = [ [SOC, ...], ... ];
            soc = 0
            match_charger = re.search(r"Charger_Data\s*=\s*\[\s*\[(\d+),", js_content)
            if match_charger:
                soc = int(match_charger.group(1))

            # --- MAPPING ---
            # Index 16: Battery Power (+ Discharge, - Charge)
            # Index 21: Grid Power (+ Import, - Export) - Based on your tests
            # Index 29: House Consumption? - Based on logic
            
            bat_power = data[16] if len(data) > 16 else 0
            grid_power = data[21] if len(data) > 21 else 0
            house_power = data[29] if len(data) > 29 else 0
            
            # Debug Output in Dry Run to verify live data
            if self.dry_run:
                print(f"LIVE CHECK -> Grid: {grid_power} W | Bat: {bat_power} W | SOC: {soc}%")

            payload = {
                "timestamp": time.time(),
                "soc": soc,
                "grid_power": grid_power,
                "battery_power": bat_power,
                "house_consumption": house_power,
                # Helper values for Home Assistant Energy Dashboard
                "grid_import": grid_power if grid_power > 0 else 0,
                "grid_export": abs(grid_power) if grid_power < 0 else 0,
                "bat_discharge": bat_power if bat_power > 0 else 0,
                "bat_charge": abs(bat_power) if bat_power < 0 else 0,
            }
            return payload

        except Exception as e:
            logger.error(f"Parsing Error: {e}")
            return None

    def run(self, interval):
        logger.info(f"Starting loop. Target: {self.base_url}")
        while True:
            js_data = self.fetch_data()
            if js_data:
                payload = self.parse_data(js_data)
                if payload and not self.dry_run:
                    self.client.publish(self.mqtt_topic, json.dumps(payload))
                    # logger.info(f"Sent: Grid {payload['grid_power']}W | Bat {payload['battery_power']}W")
            
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--ip', type=str, default=DEFAULT_VARTA_IP)
    parser.add_argument('--mqtt-host', type=str, default="localhost")
    parser.add_argument('--mqtt-user', type=str, default=None)
    parser.add_argument('--mqtt-pass', type=str, default=None)
    
    args = parser.parse_args()

    bridge = VartaBridge(
        ip=args.ip, 
        mqtt_broker=args.mqtt_host, 
        mqtt_port=1883, 
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_pass,
        dry_run=args.dry_run
    )
    
    bridge.run(DEFAULT_INTERVAL)