"""Isolated real-API browser fixture. No provider, production database or reset endpoint."""
import os
import tempfile
from pathlib import Path

os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_ENABLED"] = "false"
os.environ["SEED_SAMPLE_DATA"] = "false"
os.environ["ALLOWED_ORIGINS"] = "http://127.0.0.1:5175"
import database
import main
import uvicorn

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix=".test-tmp-integration-", dir=root) as directory:
        database.DB_PATH = Path(directory) / "audit.db"
        uvicorn.run(main.app, host="127.0.0.1", port=8011)
