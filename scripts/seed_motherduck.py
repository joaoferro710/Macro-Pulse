"""Seed script: popula o MotherDuck com dados historicos (rodar uma vez).

Uso:
    MOTHERDUCK_TOKEN=<token> python scripts/seed_motherduck.py
    # ou com .env configurado:
    python scripts/seed_motherduck.py
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
LOGGER = logging.getLogger(__name__)


def main() -> None:
    from ingestion.loader import initialize_db, load_all

    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        LOGGER.error("MOTHERDUCK_TOKEN nao encontrado. Configure no .env ou passe como variavel de ambiente.")
        sys.exit(1)

    LOGGER.info("Inicializando schema no MotherDuck...")
    initialize_db()

    LOGGER.info("Carregando dados historicos desde 2010-01-01...")
    counts = load_all(start_date="2010-01-01")
    for source, total in counts.items():
        LOGGER.info("  %s: %s linhas inseridas", source, total)

    LOGGER.info("Seed concluido com sucesso.")


if __name__ == "__main__":
    main()
