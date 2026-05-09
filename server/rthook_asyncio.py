# rthook_asyncio.py
import sys
if sys.platform == "win32" and getattr(sys, "frozen", False):
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
