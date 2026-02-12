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
DEFAULT_INTERVAL = 10 

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VartaBridge:
    def __init__(self, ip, mqtt_broker, mqtt_port, mqtt_user, mqtt_password, dry_run=False):
        # CHANGED: We now target the JS file
        self.url = f"http://{ip}/cgi/ems_data.js"
        self.dry_run = dry_run
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = "energy/varta/status"
        
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
        else:
            logger.info("--- DRY RUN MODE ACTIVATED (No MQTT) ---")

    def fetch_data(self):
        try:
            response = requests.get(self.url, timeout=5)
            response.raise_for_status()
            return response.text # We want the text string, not binary
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from Varta: {e}")
            return None

    def parse_js_data(self, js_content):
        """
        Parses Varta JS format using Regex.
        Finds 'WR_Data = [ ... ];' and extracts values.
        """
        try:
            # 1. Extract WR_Data array string
            # Looks for: WR_Data = [ numbers... ];
            match = re.search(r"WR_Data\s*=\s*\[(.*?)\];", js_content, re.DOTALL)
            
            if not match:
                logger.error("Could not find WR_Data pattern in response")
                return None

            # 2. Convert string list to Python List
            # Remove quotes, newlines, and split by comma
            raw_values = match.group(1).replace('"', '').replace('\n', '').split(',')
            
            # Convert to numbers (integers usually)
            # We filter out non-numeric items just in case (like IP addresses sometimes in there)
            wr_data = []
            for v in raw_values:
                try:
                    wr_data.append(int(v))
                except ValueError:
                    wr_data.append(0) # or keep string if needed

            # --- DEBUGGING MAPPING ---
            # This helps us identify which index is what.
            # Common Varta Mappings:
            # Index 16: Active Power (Battery)
            # Index 17: Apparent Power?
            # Index 21: Grid Power?
            # SOC is usually inside Charger_Data, but let's grab WR_Data mainly first.
            
            # 3. Extract SOC from Charger_Data (It is usually the first element of the first nested array)
            # Structure: Charger_Data = [ [SOC, ...], ... ];
            soc = 0
            match_charger = re.search(r"Charger_Data\s*=\s*\[\s*\[(\d+),", js_content)
            if match_charger:
                soc = int(match_charger.group(1))

            # --- VALUE MAPPING ---
            # Based on your snippet:
            # Index 16 is Battery (0 in your snippet)
            # Index 21 is likely Grid/House Load (499 in your snippet)
            
            battery_power = wr_data[16] # +Discharge / -Charge
            grid_power = wr_data[21]    # Check this index!
            
            # Calculate Charge/Discharge for HA
            if battery_power < 0:
                power_charge = abs(battery_power)
                power_discharge = 0
                state_str = "Charging"
            else:
                power_charge = 0
                power_discharge = battery_power
                state_str = "Discharging" if battery_power > 0 else "Idle"

            payload = {
                "timestamp": time.time(),
                "soc": soc,
                "battery_power_w": battery_power,
                "grid_power_w": grid_power, # This might need adjustment after you test
                "charge_power_w": power_charge,
                "discharge_power_w": power_discharge,
                "status_text": state_str,
                # Debug fields to help us identify the right index
                "DEBUG_INDEX_16 (Bat?)": wr_data[16] if len(wr_data) > 16 else None,
                "DEBUG_INDEX_17": wr_data[17] if len(wr_data) > 17 else None,
                "DEBUG_INDEX_21 (Grid?)": wr_data[21] if len(wr_data) > 21 else None,
            }
            return payload

        except Exception as e:
            logger.error(f"Parsing Error: {e}")
            return None

    def run(self, interval):
        logger.info(f"Starting loop. Target: {self.url} | Interval: {interval}s")
        while True:
            js_data = self.fetch_data()
            if js_data:
                payload = self.parse_js_data(js_data)
                if payload:
                    if self.dry_run:
                        print(json.dumps(payload, indent=2))
                    else:
                        # Clean payload for MQTT (remove debug keys if you want)
                        self.client.publish(self.mqtt_topic, json.dumps(payload))
                        logger.info(f"Sent: SOC {payload['soc']}% | Bat {payload['battery_power_w']}W | Grid {payload['grid_power_w']}W")
            
            time.sleep(interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--ip', type=str, default=DEFAULT_VARTA_IP)
    parser.add_argument('--mqtt-host', type=str, default="localhost")
    
    args = parser.parse_args()

    bridge = VartaBridge(
        ip=args.ip, 
        mqtt_broker=args.mqtt_host, 
        mqtt_port=1883, 
        mqtt_user=None, 
        mqtt_password=None, 
        dry_run=args.dry_run
    )
    
    bridge.run(DEFAULT_INTERVAL)