import threading
import webview
from app import app
import time
import screeninfo

def run_flask():
    print(">> Lancement du serveur Flask...")
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

if __name__ == "__main__":
    print(">> Lancement de app_gui.py...")

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    time.sleep(2)

    screen = screeninfo.get_monitors()[0]
    largeur = int(screen.width * 0.9)
    hauteur = int(screen.height * 0.9)

    # MODE DEBUG ici 👇
    webview.create_window(
        "Application des inscriptions en ligne",
        "http://127.0.0.1:5000",
        width=largeur,
        height=hauteur,
        resizable=True
    )
    webview.start(debug=False)  # <--- très important
































