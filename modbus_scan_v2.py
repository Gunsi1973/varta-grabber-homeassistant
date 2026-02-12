# Wir importieren nur den Client, den Rest machen wir mit Standard-Python
from pymodbus.client import ModbusTcpClient
import sys

# --- Konfiguration ---
IP = "192.168.1.58"
PORT = 502
START_REGISTER = 1060  # Startbereich für Varta
COUNT = 20             # Anzahl Register

def scan_modbus():
    print(f"--- Verbinde zu {IP}:{PORT} ---")
    
    # Der Import-Pfad hat sich in v3 geändert, wir fangen beide Fälle ab
    try:
        client = ModbusTcpClient(IP, port=PORT)
    except Exception:
        # Fallback für ältere Versionen
        from pymodbus.client.sync import ModbusTcpClient
        client = ModbusTcpClient(IP, port=PORT)

    if not client.connect():
        print("❌ Verbindung fehlgeschlagen! Ist Port 502 wirklich offen?")
        return

    try:
        # Wir lesen Holding Register (Slave ID 1 ist Standard bei Varta)
        # Hinweis: Manche Varta Systeme nutzen Unit-ID 1, manche 255.
        rr = client.read_holding_registers(START_REGISTER, COUNT, slave=1)
        
        if rr.isError():
            print(f"Fehler beim Lesen (Slave 1). Fehlercode: {rr}")
            # Optional: Versuch mit Slave 0 oder 255 falls 1 nicht geht
        else:
            print(f"\n--- Scan Bereich {START_REGISTER} bis {START_REGISTER + COUNT - 1} ---")
            print(f"{'Reg':<6} | {'UInt16':<8} | {'Int16 (Signed)':<15} | {'Mögliche Bedeutung'}")
            print("-" * 60)

            for i, val in enumerate(rr.registers):
                reg_num = START_REGISTER + i
                
                # Manuelle Umrechnung in Signed Int (16 Bit)
                # Wenn Wert > 32767, dann ist es eine negative Zahl (Zweierkomplement)
                val_signed = val if val < 0x8000 else val - 0x10000
                
                # Deutungshilfe
                hint = ""
                if reg_num == 1065: hint = "State?"
                if reg_num == 1066: hint = "Leistung (P)?"
                if reg_num == 1068: hint = "SOC (%)?"
                if reg_num == 1078: hint = "Netz (Grid)?"

                # Nur Zeilen mit Werten anzeigen (oder die "Verdächtigen")
                if val != 0 or reg_num in [1065, 1066, 1068, 1078]:
                    print(f"{reg_num:<6} | {val:<8} | {val_signed:<15} | {hint}")

    except Exception as e:
        print(f"Ein Fehler ist aufgetreten: {e}")
    finally:
        client.close()
        print("\n--- Fertig ---")

if __name__ == "__main__":
    scan_modbus()