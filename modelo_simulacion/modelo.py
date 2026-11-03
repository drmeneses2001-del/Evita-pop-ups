"""Microsimulación individual de la detención del descenso en el segundo periodo del parto.

Compara estrategias de manejo ante una sospecha de detención en nulíparas a término con
dilatación completa:

  E1  Práctica actual: cesárea predominante (instrumentación con frecuencia de referencia baja).
  E2  Tiempo adecuado de expulsivo y cambios de posición; si no nace -> cesárea.
  E3  E2 + rotación manual de OP/OT.
  E4  E3 + parto instrumentado (ventosa o fórceps) si la paciente es elegible y el operador
      alcanza la competencia requerida; si el instrumento falla -> cesárea.

Todas las probabilidades vienen de parametros.yaml. Este es un prototipo: muchos parámetros
son SUPUESTOS que deben calibrarse con la auditoría local (Fase 1a). Los resultados son
ilustrativos y no deben usarse para decisiones clínicas individuales.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

RUTA = Path(__file__).resolve().parent
ESTRATEGIAS = ["E1", "E2", "E3", "E4"]
DESENLACES = ["cesarea", "espontaneo", "ventosa", "forceps", "oasis", "hic",
              "trauma_neonatal_grave", "extension_histerotomia"]


def cargar_parametros(ruta: Path | None = None) -> dict:
    with open(ruta or RUTA / "parametros.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parametros_inciertos(cfg: dict) -> dict[str, dict]:
    """Aplana los parámetros con distribución (excluye política y pesos)."""
    planos = {}
    for grupo, items in cfg.items():
        if grupo in ("politica", "pesos_dano"):
            continue
        for nombre, d in items.items():
            planos[nombre] = d
    return planos


def valores_base(cfg: dict) -> dict[str, float]:
    return {k: float(v["base"]) for k, v in parametros_inciertos(cfg).items()}


def muestrear(cfg: dict, n: int, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """n conjuntos de parámetros para el análisis probabilístico."""
    out = {}
    for k, d in parametros_inciertos(cfg).items():
        tipo, a, b = d["dist"]
        if tipo == "uniforme":
            out[k] = rng.uniform(a, b, n)
        elif tipo == "lognormal":
            out[k] = np.exp(rng.normal(a, b, n))
        else:
            raise ValueError(f"Distribución desconocida: {tipo}")
    return out


@dataclass
class Politica:
    competencia_minima_plano_medio: float = 0.7
    instrumento_primero: str = "ventosa"


def simular(p: dict[str, float], estrategia: str, competencia: float, n: int,
            rng: np.random.Generator, politica: Politica | None = None) -> dict[str, float]:
    """Simula n mujeres con un conjunto fijo de parámetros p. Devuelve tasas por mujer."""
    pol = politica or Politica()
    c = float(competencia)

    # Atributos individuales
    medio = rng.random(n) < p["p_plano_medio"]
    malpos = rng.random(n) < p["p_mala_posicion"]
    prematuro = rng.random(n) < p["p_diag_prematuro"]
    urgente = rng.random(n) < p["p_urgencia_fetal"]

    via = np.full(n, "cesarea", dtype=object)
    pendiente = np.ones(n, dtype=bool)   # aún sin nacer

    if estrategia == "E1":
        inst = pendiente & ~medio & (rng.random(n) < p["p_instrumentado_practica_actual"])
        via[inst] = pol.instrumento_primero
        _resolver_instrumento(p, via, inst, medio, c, rng, pol)
        return _desenlaces(p, via, medio, c, rng)

    # E2-E4: tiempo adicional solo si no hay urgencia fetal
    tiempo = pendiente & ~urgente
    # E3-E4: rotación manual de OP/OT (antes de evaluar la evolución con tiempo)
    if estrategia in ("E3", "E4"):
        rotada = tiempo & malpos & (rng.random(n) < p["p_exito_rotacion"])
        malpos = malpos & ~rotada
    p_ve = np.where(prematuro, p["p_ve_tiempo_prematuro"],
                    np.where(malpos, p["p_ve_tiempo_verdadera_op"], p["p_ve_tiempo_verdadera_oa"]))
    nace = tiempo & (rng.random(n) < p_ve)
    via[nace] = "espontaneo"
    pendiente &= ~nace

    if estrategia == "E4":
        elegible = pendiente & (~medio | (c >= pol.competencia_minima_plano_medio))
        via[elegible] = pol.instrumento_primero
        _resolver_instrumento(p, via, elegible, medio, c, rng, pol)

    return _desenlaces(p, via, medio, c, rng)


def _resolver_instrumento(p, via, mascara, medio, c, rng, pol):
    """Aplica la probabilidad de falla; si falla -> cesárea (sin instrumentación secuencial)."""
    falla = p["falla_ventosa_plano_bajo"] * np.exp(p["k_competencia_falla"] * (0.5 - c))
    if pol.instrumento_primero == "forceps":
        falla = falla * p["rr_falla_forceps_vs_ventosa"]
    falla = np.where(medio, falla * p["mult_falla_plano_medio"], falla)
    falla = np.clip(falla, 0, 0.95)
    fallo = mascara & (rng.random(len(via)) < falla)
    via[fallo] = "cesarea"


def _desenlaces(p, via, medio, c, rng) -> dict[str, float]:
    n = len(via)
    ces = via == "cesarea"
    esp = via == "espontaneo"
    ven = via == "ventosa"
    forc = via == "forceps"
    inst = ven | forc
    m_trauma = np.exp(p["k_competencia_trauma"] * (0.5 - c))

    p_oasis = np.zeros(n)
    p_oasis[esp] = p["oasis_espontaneo"]
    p_oasis[ven] = p["oasis_ventosa"] * m_trauma
    p_oasis[forc] = p["oasis_ventosa"] * p["rr_oasis_forceps_vs_ventosa"] * m_trauma

    p_hic = np.zeros(n)
    p_hic[esp] = p["hic_espontaneo"]
    p_hic[ven] = p["hic_ventosa"]
    p_hic[forc] = p["hic_forceps"]
    p_hic[ces] = p["hic_cesarea_trabajo_parto"]

    p_tr = np.zeros(n)
    p_tr[ces] = p["trauma_grave_cesarea"]
    mult = np.where(medio, p["mult_trauma_instrumento_medio"], p["mult_trauma_instrumento_bajo"])
    p_tr[inst] = (p["trauma_grave_cesarea"] * mult * m_trauma)[inst]
    p_tr[esp] = p["trauma_grave_cesarea"] * p["mult_trauma_espontaneo"]
    p_tr = np.clip(p_tr, 0, 1)

    p_ext = np.where(ces, p["extension_histerotomia_cesarea_expulsivo"], 0.0)

    # Las vías se simulan individualmente; los eventos raros se registran como riesgo esperado
    # por mujer (promedio de probabilidades individuales) para reducir el error de Monte Carlo.
    return {
        "cesarea": ces.mean(),
        "espontaneo": esp.mean(),
        "ventosa": ven.mean(),
        "forceps": forc.mean(),
        "oasis": p_oasis.mean(),
        "hic": p_hic.mean(),
        "trauma_neonatal_grave": p_tr.mean(),
        "extension_histerotomia": p_ext.mean(),
    }


def indice_dano(res: dict[str, float], pesos: dict[str, float]) -> float:
    """Daño ponderado por mujer (pesos = juicio de valor del comité)."""
    return sum(pesos[k] * res[k] for k in pesos)
