import asyncio
import logging

from example.main import main

logger = logging.getLogger("root")

if __name__ == "__main__":
    asyncio.run(main())
