import time
import json
import logging
import argparse
import sys
import xml.etree.ElementTree as ET
import requests
import paho.mqtt.client as mqtt

# --- Configuration ---
# Defaults (can be overridden by environment variables or arguments in a later version)
DEFAULT_VARTA_IP = "192.168.1.58" 
DEFAULT_INTERVAL = 10  # Seconds

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VartaBridge:
    def __init__(self, ip, mqtt_broker, mqtt_port, mqtt_user, mqtt_password, dry_run=False):
        self.url = f"http://{ip}/cgi/ems_data.xml"
        self.dry_run = dry_run
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.mqtt_topic = "energy/varta/status"
        
        # MQTT Client Setup
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

    def fetch_xml(self):
        try:
            response = requests.get(self.url, timeout=5)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching data from Varta: {e}")
            return None

    def parse_data(self, xml_content):
        """
        Parses Varta XML. 
        Expected format: <root ...><inverter ...><var name="P" value="..."/>...
        """
        try:
            root = ET.fromstring(xml_content)
            data = {}
            
            # Extract attributes from 'var' tags
            for var in root.findall(".//var"):
                name = var.get("name")
                value = var.get("value")
                # Attempt to convert numbers
                try:
                    if "." in value:
                        data[name] = float(value)
                    else:
                        data[name] = int(value)
                except (ValueError, TypeError):
                    data[name] = value
            
            # --- Logic Calculation for Home Assistant ---
            # 'P' is usually active power. 
            # Logic assumption: Positive = Discharging (Battery gives power), Negative = Charging (Battery takes power)
            raw_power = data.get("P", 0)
            
            # Separate into Charge/Discharge for HA Energy Dashboard
            # If raw_power is negative, we are charging. Convert to positive for the sensor.
            # If raw_power is positive, we are discharging.
            
            if raw_power < 0:
                power_charge = abs(raw_power)
                power_discharge = 0
                state_str = "Charging"
            else:
                power_charge = 0
                power_discharge = raw_power
                state_str = "Discharging" if raw_power > 0 else "Idle"

            payload = {
                "timestamp": root.get("Timestamp"),
                "soc": data.get("SOC", 0),
                "state_id": data.get("State", 0),
                "capacity_wh": data.get("Capacity", 0),
                "grid_power_w": raw_power,        # Raw value (can be +/-)
                "charge_power_w": power_charge,   # Always +
                "discharge_power_w": power_discharge, # Always +
                "status_text": state_str
            }
            return payload

        except ET.ParseError as e:
            logger.error(f"XML Parse Error: {e}")
            return None

    def run(self, interval):
        logger.info(f"Starting loop. Target: {self.url} | Interval: {interval}s")
        while True:
            xml_data = self.fetch_xml()
            if xml_data:
                payload = self.parse_data(xml_data)
                if payload:
                    if self.dry_run:
                        # Pretty print for console verification
                        print(json.dumps(payload, indent=2))
                    else:
                        # Send to MQTT
                        self.client.publish(self.mqtt_topic, json.dumps(payload))
                        logger.info(f"Published: SOC {payload['soc']}% | Power {payload['grid_power_w']}W")
            
            time.sleep(interval)

if __name__ == "__main__":
    # Simple Argument Parsing
    parser = argparse.ArgumentParser(description='Varta Battery MQTT Bridge')
    parser.add_argument('--dry-run', action='store_true', help='Print to console instead of MQTT')
    parser.add_argument('--ip', type=str, default=DEFAULT_VARTA_IP, help='Varta Battery IP')
    parser.add_argument('--mqtt-host', type=str, default="localhost", help='MQTT Broker Host')
    
    args = parser.parse_args()

    # Initialize Bridge
    bridge = VartaBridge(
        ip=args.ip, 
        mqtt_broker=args.mqtt_host, 
        mqtt_port=1883, 
        mqtt_user=None, 
        mqtt_password=None, 
        dry_run=args.dry_run
    )
    
    bridge.run(DEFAULT_INTERVAL)