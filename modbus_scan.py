from pymodbus.client import ModbusTcpClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import time

# --- Konfiguration ---
IP = "192.168.1.58"
PORT = 502
START_REGISTER = 1060  # Varta "Hotzone" beginnt oft hier
COUNT = 20             # Wir lesen 20 Register am Stück

def scan_modbus():
    print(f"--- Verbinde zu {IP}:{PORT} via Modbus ---")
    client = ModbusTcpClient(IP, port=PORT)
    
    if not client.connect():
        print("❌ Verbindung fehlgeschlagen!")
        return

    try:
        # Wir lesen die "Input Register" (kann auch Holding sein, Varta nutzt oft Holding)
        # Versuch 1: Holding Register
        rr = client.read_holding_registers(START_REGISTER, COUNT, slave=1)
        
        if rr.isError():
            print("Fehler beim Lesen der Register (Holding). Versuche Input Register...")
            rr = client.read_input_registers(START_REGISTER, COUNT, slave=1)

        if not rr.isError():
            print(f"\n--- Scan Bereich {START_REGISTER} bis {START_REGISTER + COUNT} ---")
            print(f"{'Register':<10} | {'Raw (uint16)':<15} | {'Signed (int16)':<15} | {'Deutung?'}")
            print("-" * 60)

            registers = rr.registers
            for i, val in enumerate(registers):
                address = START_REGISTER + i
                
                # Umrechnung in Signed Int (für negative Werte wie Laden)
                val_signed = val if val < 32768 else val - 65536
                
                # Einfache Deutung basierend auf bekannten Varta-Belegungen
                hint = ""
                if address == 1065: hint = "System Status?"
                if address == 1066: hint = "Wirkleistung (Active Power)?"
                if address == 1068: hint = "SOC %?"
                if address == 1078: hint = "Netzleistung (Grid)?"
                
                # Filter: Zeige nur Werte an, die nicht 0 sind (ausser SOC/Status)
                if val != 0 or address in [1065, 1066, 1068, 1078]:
                    print(f"{address:<10} | {val:<15} | {val_signed:<15} | {hint}")
        else:
            print("❌ Fehler: Konnte keine Daten lesen. Evtl. falsche Unit-ID (slave=1).")

    except Exception as e:
        print(f"Absturz: {e}")
    finally:
        client.close()
        print("\n--- Verbindung geschlossen ---")

if __name__ == "__main__":
    scan_modbus()