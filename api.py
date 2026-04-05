from flask import Flask, jsonify

from collector import store


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        from datetime import datetime
        return jsonify({"status": "ok", "ts": datetime.now().isoformat()})

    @app.get("/monitors")
    def monitors():
        return jsonify(store.get_monitors())

    @app.get("/vitals")
    def all_vitals():
        return jsonify(store.get_last())

    @app.get("/vitals/<ip>")
    def one_vital(ip):
        reading = store.get_last(ip)
        if reading is None:
            return jsonify({"error": "monitor no encontrado o sin datos"}), 404
        return jsonify(reading)

    return app
