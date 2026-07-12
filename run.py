"""Entry point: `py run.py` -> http://127.0.0.1:5000

debug=False deliberately — Flask's reloader spawns a second process and
would silently drop the in-process SESSIONS dict (and any in-flight
Session) on every code save.
"""

from sequence_trainer.webapp.app import app

if __name__ == "__main__":
    app.run("127.0.0.1", 5000, debug=False)
