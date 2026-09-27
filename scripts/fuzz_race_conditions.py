import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.stream_manager import stream_manager

logging.basicConfig(level=logging.DEBUG)


async def main():
    print("Testing race conditions...")
    device = "testsrc"

    async def start_loop():
        for _ in range(100):
            await stream_manager.start_stream(device)
            await asyncio.sleep(0.01)

    async def stop_loop():
        for _ in range(100):
            await stream_manager.stop_stream(device)
            await asyncio.sleep(0.01)

    async def remove_loop():
        for _ in range(20):
            await stream_manager.remove_stream(device)
            await asyncio.sleep(0.05)

    await asyncio.gather(start_loop(), stop_loop(), remove_loop())
    print("Done testing.")


if __name__ == "__main__":
    asyncio.run(main())
