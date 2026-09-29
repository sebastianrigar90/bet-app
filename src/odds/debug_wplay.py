from pathlib import Path
import re

import pandas as pd
from bs4 import BeautifulSoup

from .wplay import WplaySource


def generate_debug_file():

    source = WplaySource(
        url="https://apuestas.wplay.co/es/PremierLeague",
        competition="premier_league",
    )

    response = source._get_response()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    rows = []
    seen = set()

    for block in source._find_blocks(soup):

        raw_text = block.get_text(
            " ",
            strip=True,
        )

        raw_text = re.sub(
            r"\s+",
            " ",
            raw_text,
        ).strip()

        if not raw_text:
            continue

        if raw_text in seen:
            continue

        seen.add(raw_text)

        decimal_values = re.findall(
            r"\b\d+\.\d+\b",
            raw_text,
        )

        cuotas = decimal_values[-3:]

        local = None
        visitante = None

        equipos = source._extract_teams(
            raw_text
        )

        if equipos:
            local, visitante = equipos

        rows.append(
            {
                "texto_original": raw_text,
                "local_detectado": local,
                "visitante_detectado": visitante,
                "valores_decimal": " | ".join(
                    cuotas
                ),
                "cantidad_decimales": len(
                    decimal_values
                ),
                "cuota_local": (
                    cuotas[0]
                    if len(cuotas) >= 1
                    else None
                ),
                "cuota_empate": (
                    cuotas[1]
                    if len(cuotas) >= 2
                    else None
                ),
                "cuota_visitante": (
                    cuotas[2]
                    if len(cuotas) >= 3
                    else None
                ),
            }
        )

    if not rows:
        raise RuntimeError(
            "No se encontraron bloques para analizar."
        )

    df = pd.DataFrame(rows)

    output = (
        Path("data")
        / "raw"
        / "odds"
        / "wplay_debug.xlsx"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_excel(
        output,
        index=False,
    )

    print("DEBUG WPLAY OK")
    print("REGISTROS:", len(df))
    print("ARCHIVO:", output)


if __name__ == "__main__":
    generate_debug_file()