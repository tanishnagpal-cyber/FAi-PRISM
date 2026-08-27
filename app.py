"""
app.py  -  Root WSGI entry point (so `gunicorn app:app` works from the repo root,
which is what Render runs by default). The real server lives in src/server.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from server import app  # noqa: E402  (Flask app object, imported for gunicorn)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
