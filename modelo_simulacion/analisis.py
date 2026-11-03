"""Ejecuta los análisis del prototipo y guarda tablas y figuras en resultados/.

Uso:  python analisis.py [--rapido]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import train_test_split

from modelo import (ESTRATEGIAS, Politica, cargar_parametros, indice_dano, muestrear,
                    parametros_inciertos, simular, valores_base)

RUTA = Path(__file__).resolve().parent
SAL = RUTA / "resultados"
SEMILLA = 20261103
NOMBRES = {"E1": "E1 Práctica actual", "E2": "E2 Tiempo + posición",
           "E3": "E3 + Rotación manual", "E4": "E4 + Instrumentado"}
COLORES = {"E1": "#7a1f3d", "E2": "#c08a2e", "E3": "#2f7d6d", "E4": "#2f5d80"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def por_mil(res):
    return {k: v * 1000 for k, v in res.items()}


def caso_base(cfg, n, pol):
    rng = np.random.default_rng(SEMILLA)
    p = valores_base(cfg)
    filas = []
    for c, etiqueta in [(0.2, "Novato"), (0.5, "Intermedio"), (0.9, "Experto")]:
        for e in ESTRATEGIAS:
            r = simular(p, e, c, n, rng, pol)
            fila = {"competencia": etiqueta, "c": c, "estrategia": e, **por_mil(r),
                    "indice_dano": indice_dano(r, cfg["pesos_dano"]) * 1000}
            filas.append(fila)
    return pd.DataFrame(filas)


def barrido_competencia(cfg, n, pol):
    rng = np.random.default_rng(SEMILLA + 1)
    p = valores_base(cfg)
    filas = []
    for c in np.round(np.arange(0, 1.0001, 0.05), 2):
        for e in ESTRATEGIAS:
            r = simular(p, e, c, n, rng, pol)
            filas.append({"c": c, "estrategia": e, **por_mil(r),
                          "indice_dano": indice_dano(r, cfg["pesos_dano"]) * 1000})
    return pd.DataFrame(filas)


def probabilistico(cfg, iteraciones, n, pol):
    """PSA: competencia muestreada U(0,1) como entrada adicional para el emulador."""
    rng = np.random.default_rng(SEMILLA + 2)
    mu = muestrear(cfg, iteraciones, rng)
    comp = rng.uniform(0, 1, iteraciones)
    filas = []
    for i in range(iteraciones):
        p = {k: v[i] for k, v in mu.items()}
        fila = {**p, "competencia": comp[i]}
        for e in ESTRATEGIAS:
            r = simular(p, e, comp[i], n, rng, pol)
            for k, v in r.items():
                fila[f"{e}_{k}"] = v * 1000
            fila[f"{e}_dano"] = indice_dano(r, cfg["pesos_dano"]) * 1000
        filas.append(fila)
    return pd.DataFrame(filas)


def evpi(df, mascara):
    """Valor esperado de la información perfecta (en unidades de daño ponderado por 1,000)."""
    d = df.loc[mascara, [f"{e}_dano" for e in ESTRATEGIAS]].to_numpy()
    return float(d.mean(axis=0).min() - d.min(axis=1).mean())


def emulador(df, cfg):
    """Emulador de aprendizaje automático (gradient boosting) de la diferencia de daño E4 - E3
    y de las cesáreas evitadas E4 vs E1; importancia por permutación y Sobol de 1.er orden."""
    entradas = list(parametros_inciertos(cfg).keys()) + ["competencia"]
    X = df[entradas].to_numpy()
    objetivos = {
        "delta_dano_E4_vs_E3": (df["E4_dano"] - df["E3_dano"]).to_numpy(),
        "cesareas_evitadas_E4_vs_E1": (df["E1_cesarea"] - df["E4_cesarea"]).to_numpy(),
    }
    salida = {}
    for nombre, y in objetivos.items():
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=SEMILLA)
        gb = GradientBoostingRegressor(n_estimators=400, max_depth=3, learning_rate=0.05,
                                       subsample=0.8, random_state=SEMILLA).fit(Xtr, ytr)
        r2 = gb.score(Xte, yte)
        imp = permutation_importance(gb, Xte, yte, n_repeats=10, random_state=SEMILLA)
        # Sobol de primer orden con el emulador (estimador por partición en 20 cuantiles)
        # Muestras nuevas e independientes de las distribuciones a priori (no re-muestreo del PSA)
        rng = np.random.default_rng(SEMILLA + 3)
        mu = muestrear(cfg, 50000, rng)
        base = np.column_stack([mu[k] for k in entradas[:-1]] + [rng.uniform(0, 1, 50000)])
        yb = gb.predict(base)
        var = yb.var()
        sobol = {}
        for j, nom in enumerate(entradas):
            bins = np.quantile(base[:, j], np.linspace(0, 1, 26))
            idx = np.clip(np.digitize(base[:, j], bins[1:-1]), 0, 24)
            medias = np.array([yb[idx == b].mean() for b in range(25)])
            sobol[nom] = float(medias.var() / var) if var > 0 else 0.0
        salida[nombre] = {
            "r2_prueba": float(r2),
            "importancia": {entradas[j]: float(imp.importances_mean[j]) for j in range(len(entradas))},
            "sobol_primer_orden": sobol,
        }
    return salida


def figuras(base, barr, psa, emu, cfg):
    # Figura 1: vías de nacimiento por estrategia, competencia intermedia
    b = base[base.c == 0.5].set_index("estrategia")
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    izq = np.zeros(4)
    for col, color, et in [("espontaneo", "#2f7d6d", "Espontáneo"), ("ventosa", "#2f5d80", "Ventosa"),
                           ("forceps", "#c08a2e", "Fórceps"), ("cesarea", "#7a1f3d", "Cesárea")]:
        v = b.loc[ESTRATEGIAS, col].to_numpy() / 10
        ax.barh([NOMBRES[e] for e in ESTRATEGIAS], v, left=izq, color=color, label=et)
        for i, (x, w) in enumerate(zip(izq, v)):
            if w > 4:
                ax.text(x + w / 2, i, f"{w:.0f}", ha="center", va="center", color="white", fontsize=8)
        izq += v
    ax.invert_yaxis(); ax.set_xlabel("% de mujeres con sospecha de detención"); ax.set_xlim(0, 100)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(SAL / "fig1_vias.png", dpi=200); plt.close(fig)

    # Figura 2: barrido de competencia E4 vs E3 y E1
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
    for e in ESTRATEGIAS:
        d = barr[barr.estrategia == e]
        axs[0].plot(d.c, d.cesarea, color=COLORES[e], label=NOMBRES[e])
        axs[1].plot(d.c, d.trauma_neonatal_grave, color=COLORES[e])
        axs[2].plot(d.c, d.indice_dano, color=COLORES[e])
    axs[0].set_title("Cesáreas /1,000", fontsize=9)
    axs[1].set_title("Trauma neonatal grave /1,000", fontsize=9)
    axs[2].set_title("Índice de daño ponderado /1,000", fontsize=9)
    for a in axs:
        a.set_xlabel("Competencia del operador (0-1)")
        a.axvline(cfg["politica"]["competencia_minima_plano_medio"], color="#999", ls=":", lw=1)
    axs[0].legend(fontsize=6.5, frameon=False)
    fig.tight_layout(); fig.savefig(SAL / "fig2_competencia.png", dpi=200); plt.close(fig)

    # Figura 3: PSA, plano cesáreas evitadas vs daño adicional (E4 vs E1), coloreado por competencia
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    sc = ax.scatter(psa["E1_cesarea"] - psa["E4_cesarea"], psa["E4_dano"] - psa["E1_dano"],
                    c=psa["competencia"], cmap="viridis", s=6, alpha=0.7)
    ax.axhline(0, color="#555", lw=0.8)
    ax.set_xlabel("Cesáreas evitadas por 1,000 (E4 frente a E1)")
    ax.set_ylabel("Δ índice de daño por 1,000\n(<0 = menos daño con E4)")
    fig.colorbar(sc, ax=ax, label="Competencia")
    fig.tight_layout(); fig.savefig(SAL / "fig3_psa.png", dpi=200); plt.close(fig)

    # Figura 4: probabilidad de que E4 sea la estrategia de menor daño según el peso de la cesárea
    comps = ["trauma_neonatal_grave", "hic", "oasis", "extension_histerotomia", "cesarea"]
    ws = np.linspace(0, 0.10, 21)
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    for (lo, hi), color, et in [((0, 0.4), "#7a1f3d", "Competencia baja (<0.4)"),
                                ((0.4, 0.7), "#c08a2e", "Media (0.4-0.7)"),
                                ((0.7, 1.01), "#2f5d80", "Alta (>0.7)")]:
        d = psa[(psa.competencia >= lo) & (psa.competencia < hi)]
        probs = []
        for w in ws:
            pesos = dict(cfg["pesos_dano"]); pesos["cesarea"] = w
            m = np.column_stack([sum(pesos[k] * d[f"{e}_{k}"] for k in comps) for e in ESTRATEGIAS])
            probs.append((m.argmin(axis=1) == 3).mean())
        ax.plot(ws, probs, color=color, label=et)
    ax.axvline(cfg["pesos_dano"]["cesarea"], color="#999", ls=":", lw=1)
    ax.set_xlabel("Peso asignado a una cesárea\n(1 = un trauma neonatal grave)")
    ax.set_ylabel("P(E4 = menor daño)"); ax.set_ylim(-0.02, 1.02)
    ax.legend(fontsize=6.5, frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(SAL / "fig4_aceptabilidad.png", dpi=200); plt.close(fig)

    # Figura 5: sensibilidad global (Sobol 1.er orden del emulador), top 10
    s = pd.Series(emu["delta_dano_E4_vs_E3"]["sobol_primer_orden"]).sort_values().tail(10)
    fig, ax = plt.subplots(figsize=(5.2, 3.0))
    tipos = {k: v["tipo"] for k, v in parametros_inciertos(cfg).items()}
    cols = ["#999" if k == "competencia" else ("#2f5d80" if tipos.get(k) == "literatura" else "#c08a2e")
            for k in s.index]
    ax.barh(s.index, s.values, color=cols)
    ax.set_xlabel("Índice de Sobol de 1.er orden")
    ax.set_title("Qué explica la diferencia de daño E4 − E3\n(azul = literatura · ocre = supuesto · gris = competencia)",
                 fontsize=7.5, loc="right")
    fig.tight_layout(); fig.savefig(SAL / "fig5_sobol.png", dpi=200); plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true", help="Corrida corta para pruebas")
    a = ap.parse_args()
    SAL.mkdir(exist_ok=True)
    cfg = cargar_parametros()
    pol = Politica(cfg["politica"]["competencia_minima_plano_medio"], cfg["politica"]["instrumento_primero"])
    n_base, n_barr, it, n_psa = (20000, 10000, 200, 5000) if a.rapido else (200000, 100000, 2000, 20000)

    base = caso_base(cfg, n_base, pol)
    barr = barrido_competencia(cfg, n_barr, pol)
    psa = probabilistico(cfg, it, n_psa, pol)
    emu = emulador(psa, cfg)

    base.to_csv(SAL / "caso_base.csv", index=False)
    barr.to_csv(SAL / "barrido_competencia.csv", index=False)
    psa.to_csv(SAL / "psa.csv", index=False)

    # Umbral de competencia: primera c donde E4 tiene menor índice de daño que E3 (caso base)
    piv = barr.pivot(index="c", columns="estrategia", values="indice_dano")
    mejor = piv.idxmin(axis=1)
    umbral = next((float(c) for c in piv.index if (piv.loc[c, "E4"] < piv.loc[c, "E3"])), None)

    # Desenlace sin pesos: cesáreas evitadas por cada trauma neonatal grave adicional (E4 vs E3)
    e3 = barr[barr.estrategia == "E3"].set_index("c"); e4 = barr[barr.estrategia == "E4"].set_index("c")
    intercambio = pd.DataFrame({
        "cesareas_evitadas_E4_vs_E3": e3.cesarea - e4.cesarea,
        "trauma_grave_adicional": e4.trauma_neonatal_grave - e3.trauma_neonatal_grave,
        "hic_adicional": e4.hic - e3.hic,
        "oasis_adicional": e4.oasis - e3.oasis,
    })
    intercambio["cesareas_por_trauma_grave"] = np.where(
        intercambio.trauma_grave_adicional > 0,
        intercambio.cesareas_evitadas_E4_vs_E3 / intercambio.trauma_grave_adicional, np.inf)
    intercambio.to_csv(SAL / "intercambio_E4_vs_E3.csv")

    # Sensibilidad a los pesos (juicios de valor): umbral de competencia según el peso de la cesárea
    sens_pesos = {}
    comps = ["trauma_neonatal_grave", "hic", "oasis", "extension_histerotomia", "cesarea"]
    for w in [0.01, 0.02, 0.04, 0.08, 0.15]:
        pesos = dict(cfg["pesos_dano"]); pesos["cesarea"] = w
        idx = {e: sum(pesos[k] * barr[barr.estrategia == e].set_index("c")[k] for k in comps) for e in ESTRATEGIAS}
        dfi = pd.DataFrame(idx)
        um = next((float(c) for c in dfi.index if dfi.loc[c, "E4"] < dfi.loc[c, "E3"]), None)
        sens_pesos[str(w)] = {"umbral_competencia_E4_mejor_que_E3": um,
                              "mejor_en_c0.2": dfi.loc[0.2].idxmin(), "mejor_en_c0.5": dfi.loc[0.5].idxmin(),
                              "mejor_en_c0.9": dfi.loc[0.9].idxmin()}
        # EVPI con estos pesos (PSA)
        d = psa.copy()
        for e in ESTRATEGIAS:
            d[f"{e}_dano"] = sum(pesos[k] * d[f"{e}_{k}"] for k in comps)
        sens_pesos[str(w)]["evpi_por_1000_global"] = evpi(d, np.ones(len(d), bool))

    # Política de plano medio: operador experto (c=0.9) con instrumentación solo en plano bajo vs también en medio
    rng = np.random.default_rng(SEMILLA + 4)
    pb = valores_base(cfg)
    solo_bajo = simular(pb, "E4", 0.9, n_base, rng, Politica(1.01, pol.instrumento_primero))
    con_medio = simular(pb, "E4", 0.9, n_base, rng, Politica(0.7, pol.instrumento_primero))
    plano_medio = {k: (con_medio[k] - solo_bajo[k]) * 1000 for k in con_medio}
    # Ventosa primero vs fórceps primero (c=0.9, plano bajo y medio permitidos)
    forc = simular(pb, "E4", 0.9, n_base, rng, Politica(0.7, "forceps"))
    vent = simular(pb, "E4", 0.9, n_base, rng, Politica(0.7, "ventosa"))
    forceps_vs_ventosa = {k: (forc[k] - vent[k]) * 1000 for k in forc}

    resumen = {
        "plano_medio_experto_(con_medio_menos_solo_bajo)_por_1000": plano_medio,
        "forceps_primero_menos_ventosa_primero_c0.9_por_1000": forceps_vs_ventosa,
        "umbral_competencia_E4_menor_dano_que_E3": umbral,
        "estrategia_menor_dano_por_competencia": mejor.to_dict(),
        "evpi_por_1000": {
            "competencia_baja_(<0.4)": evpi(psa, psa.competencia < 0.4),
            "competencia_media_(0.4-0.7)": evpi(psa, psa.competencia.between(0.4, 0.7)),
            "competencia_alta_(>0.7)": evpi(psa, psa.competencia > 0.7),
        },
        "psa_cesareas_evitadas_E4_vs_E1": {
            "media": float((psa.E1_cesarea - psa.E4_cesarea).mean()),
            "p2.5": float((psa.E1_cesarea - psa.E4_cesarea).quantile(0.025)),
            "p97.5": float((psa.E1_cesarea - psa.E4_cesarea).quantile(0.975)),
        },
        "psa_cesareas_evitadas_E3_vs_E1": {
            "media": float((psa.E1_cesarea - psa.E3_cesarea).mean()),
            "p2.5": float((psa.E1_cesarea - psa.E3_cesarea).quantile(0.025)),
            "p97.5": float((psa.E1_cesarea - psa.E3_cesarea).quantile(0.975)),
        },
        "sensibilidad_pesos_cesarea": sens_pesos,
        "intercambio_E4_vs_E3_c0.5": intercambio.loc[0.5].to_dict(),
        "intercambio_E4_vs_E3_c0.9": intercambio.loc[0.9].to_dict(),
        "intercambio_E4_vs_E3_c0.2": intercambio.loc[0.2].to_dict(),
        "emulador": emu,
        "corridas": {"n_caso_base": n_base, "n_barrido": n_barr, "iteraciones_psa": it, "n_por_iteracion": n_psa},
    }
    (SAL / "resumen.json").write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    figuras(base, barr, psa, emu, cfg)
    print(json.dumps({k: v for k, v in resumen.items() if k not in ("emulador", "estrategia_menor_dano_por_competencia")}, indent=1, ensure_ascii=False, default=str))
    for k, v in emu.items():
        top = sorted(v["sobol_primer_orden"].items(), key=lambda t: -t[1])[:6]
        print(k, "R2=", round(v["r2_prueba"], 3), [(n, round(s, 3)) for n, s in top])


if __name__ == "__main__":
    main()
