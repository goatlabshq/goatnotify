"""In-memory fakes for testing code that sends notifications."""


async def no_sleep(delay: float) -> None:
    """Drop-in for asyncio.sleep that makes retries instantaneous."""
