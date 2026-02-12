from pymodbus.client import ModbusTcpClient
import sys

# --- Konfiguration ---
IP = "192.168.1.58"
PORT = 502
START_REGISTER = 1060  # Startbereich für Varta
COUNT = 20             # Anzahl Register

def scan_modbus():
    print(f"--- Verbinde zu {IP}:{PORT} (Pymodbus 3.12.0) ---")
    
    # Client für Version 3.x
    client = ModbusTcpClient(IP, port=PORT)

    if not client.connect():
        print("❌ Verbindung fehlgeschlagen! Port 502 nicht erreichbar.")
        return

    try:
        # Wir lesen Holding Register (Slave ID 1 ist Standard)
        rr = client.read_holding_registers(START_REGISTER, COUNT, slave=1)
        
        if rr.isError():
            print(f"❌ Fehler beim Lesen: {rr}")
        else:
            print(f"\n--- Scan Bereich {START_REGISTER} bis {START_REGISTER + COUNT - 1} ---")
            print(f"{'Reg':<6} | {'UInt16':<8} | {'Int16 (Signed)':<15} | {'Mögliche Bedeutung'}")
            print("-" * 65)

            for i, val in enumerate(rr.registers):
                reg_num = START_REGISTER + i
                
                # Manuelle Umrechnung in Signed Int (16 Bit)
                # Wenn Wert > 32767, ist es negativ (z.B. 65530 = -6)
                val_signed = val if val < 0x8000 else val - 0x10000
                
                # Deutungshilfe für Varta
                hint = ""
                if reg_num == 1065: hint = "State?"
                if reg_num == 1066: hint = "Active Power (W)?"
                if reg_num == 1068: hint = "SOC (%)?"
                if reg_num == 1078: hint = "Grid Power (W)?"

                # Zeige nur relevante Zeilen
                if val != 0 or reg_num in [1065, 1066, 1068, 1078]:
                    print(f"{reg_num:<6} | {val:<8} | {val_signed:<15} | {hint}")

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
    finally:
        client.close()
        print("\n--- Fertig ---")

if __name__ == "__main__":
    scan_modbus()