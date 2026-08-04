from dotenv import load_dotenv

# Load .env before any core submodule (database, controllers, cruds) reads
# os.getenv at import time. This package __init__ runs first for every
# `from core...` import, so it is the earliest safe place to do this.
load_dotenv()

from commons.logger import logger
