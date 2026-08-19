from __future__ import annotations

import logging
import time

import extensions
from services.channel_publication_service import PUBLICATION_QUEUE, _redis_client, process_publication, promote_scheduled
from services.service_config import enforce_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("negobot-channel-publication-worker")


def main() -> None:
    enforce_profile("channel_publication")
    extensions.init_extensions()
    queue = _redis_client()
    queue.ping()
    logger.info("Worker de publicações de Channels iniciado; fila=%s", PUBLICATION_QUEUE)
    while True:
        try:
            promoted = promote_scheduled(queue)
            if promoted:
                logger.info("Publicações agendadas promovidas: %d", promoted)
            job = queue.blpop(PUBLICATION_QUEUE, timeout=15)
            if not job:
                continue
            process_publication(str(job[1]), queue)
        except Exception:
            logger.exception("Erro no worker de publicações de Channels; a retomar em 5 segundos")
            time.sleep(5)


if __name__ == "__main__":
    main()
