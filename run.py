import os
from app import app

if __name__ == "__main__":
    port = int(os.environ.get('FLASK_RUN_PORT', 5040))
    app.run(port=port)
