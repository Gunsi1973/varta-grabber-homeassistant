import socket

IP = "192.168.1.58"
PORT = 502

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(2)
try:
    result = sock.connect_ex((IP, PORT))
    if result == 0:
        print(f"✅ BINGO! Port {PORT} (Modbus) ist OFFEN.")
        print("Wir können die Daten direkt und zuverlässig abrufen.")
    else:
        print(f"Port {PORT} ist geschlossen. Wir müssen beim Web-Interface bleiben.")
except Exception as e:
    print(f"Fehler beim Verbinden: {e}")
finally:
    sock.close()