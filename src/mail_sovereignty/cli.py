import asyncio
from pathlib import Path


def preprocess() -> None:
    from mail_sovereignty.preprocess import run

    asyncio.run(run(Path("data.json")))


def postprocess() -> None:
    from mail_sovereignty.postprocess import run

    asyncio.run(run(Path("data.json")))


def validate() -> None:
    from mail_sovereignty.validate import run

    run(Path("data.json"), Path("."), quality_gate=True)


def build_data_de() -> None:
    from mail_sovereignty.build_data_de import main

    main()


def build_site_de() -> None:
    from mail_sovereignty.build_site_de import main

    main()
