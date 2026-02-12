from pymodbus.client import ModbusTcpClient
import sys

IP = "192.168.1.58"
PORT = 502
START_REGISTER = 1065 # Scanning 1065-1080 (The hot zone)
COUNT = 15

def scan_universal():
    print(f"--- Connecting to {IP}:{PORT} ---")
    client = ModbusTcpClient(IP, port=PORT)
    if not client.connect():
        print("Connection failed.")
        return

    print(f"Scanning registers {START_REGISTER} to {START_REGISTER + COUNT}...")
    
    rr = None
    # STRATEGY 1: Standard v3.x (slave=1)
    try:
        rr = client.read_holding_registers(START_REGISTER, COUNT, slave=1)
    except TypeError:
        # STRATEGY 2: Legacy v2.x (unit=1) - This is likely what your setup needs
        try:
            print("Mode 'slave' failed, trying 'unit'...")
            rr = client.read_holding_registers(START_REGISTER, COUNT, unit=1)
        except TypeError:
            # STRATEGY 3: Positional arguments (No keywords)
            print("Mode 'unit' failed, trying positional args...")
            rr = client.read_holding_registers(START_REGISTER, COUNT, 1)

    if rr and not rr.isError():
        print("\nSUCCESS! Raw Data:")
        print(f"{'Reg':<6} | {'Value':<8} | {'Value (Signed)'}")
        for i, val in enumerate(rr.registers):
            reg = START_REGISTER + i
            val_signed = val if val < 32768 else val - 65536
            
            # Highlight likely candidates
            label = ""
            if reg == 1066: label = "<-- Battery Power"
            if reg == 1068: label = "<-- SOC"
            if reg == 1078: label = "<-- Grid Power"
            
            print(f"{reg:<6} | {val:<8} | {val_signed:<10} {label}")
    else:
        print(f"Error reading: {rr}")

    client.close()

if __name__ == "__main__":
    scan_universal()