"""Carga estilo.json (el del repo) y le mezcla encima el del usuario, solo con claves conocidas."""
import copy
import json
import os

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ESTILO_BASE = os.path.join(RAIZ, "estilo.json")


def _mezclar(base, extra, ruta=""):
    for k, v in extra.items():
        if k.startswith("_"):
            continue
        if k not in base:
            raise ValueError(f"clave desconocida en el estilo: {ruta}{k}")
        if isinstance(base[k], dict):
            if not isinstance(v, dict):
                raise ValueError(f"{ruta}{k} debe ser un objeto")
            _mezclar(base[k], v, f"{ruta}{k}.")
        else:
            base[k] = v


def cargar_estilo(ruta=None):
    with open(ESTILO_BASE, encoding="utf-8") as f:
        base = json.load(f)
    base = {k: v for k, v in base.items() if not k.startswith("_")}
    if ruta:
        with open(ruta, encoding="utf-8") as f:
            _mezclar(base, json.load(f))
    return copy.deepcopy(base)
