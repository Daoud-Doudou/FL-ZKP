# utils/zkp_utils.py
import os
import json
import math
import glob
import shlex
import subprocess
from typing import Optional
from utils.commit_integration import integrate_commitments_for_round

# -------------------------------
# Paramètres via variables d'environnement (avec valeurs par défaut)
# -------------------------------
DEFAULT_SCALE = int(os.environ.get("ZKP_SCALE", "1000000"))
DEFAULT_CHUNK = int(os.environ.get("ZKP_CHUNK", "4096"))
CIRCUIT_DIR   = os.environ.get("ZKP_CIRCUIT_DIR", "/app/zkp/avg_chunk")
PTAU_PATH     = os.environ.get("ZKP_PTAU", "/app/shared/zkp/ptau/powersOfTau28_hez_final_18.ptau")
AUTOPROVE     = os.environ.get("ZKP_AUTOPROVE", "0") == "1"
PTAU_GEN      = os.environ.get("ZKP_PTAU_GEN", "0") == "1"
PTAU_POWER    = int(os.environ.get("ZKP_PTAU_POWER", "20"))  


# -------------------------------
# Utils
# -------------------------------
def _q(x: float, scale: int) -> int:
    """Quantification avec arrondi."""
    return int(round(x * scale))


def _run(cmd: str, cwd: Optional[str] = None, stdin: Optional[str] = None) -> None:
    """
    Exécute une commande en élevant une exception si le code retour != 0.
    - stdin: si fourni, sera passé en entrée standard (str).
    """
    subprocess.run(
        shlex.split(cmd),
        cwd=cwd,
        check=True,
        input=(stdin if stdin is not None else None),
        text=True,
    )


# -------------------------------
# Ptau
# -------------------------------
def _ensure_ptau(ptau_path: str = PTAU_PATH, power: int = PTAU_POWER) -> None:
    """
    Vérifie la présence du fichier .ptau, et le génère si autorisé (ZKP_PTAU_GEN=1).
    Compatible snarkjs@0.7.5 (contribute sans options; nom/entropie via stdin).
    """
    if os.path.exists(ptau_path):
        return

    if not PTAU_GEN:
        raise RuntimeError(
            f"[ZKP] Ptau introuvable: {ptau_path} (active ZKP_PTAU_GEN=1 pour le générer)"
        )

    workdir = os.path.dirname(ptau_path)
    os.makedirs(workdir, exist_ok=True)

    pot0 = os.path.join(workdir, f"pot{power:02d}_0000.ptau")
    pot1 = os.path.join(workdir, f"pot{power:02d}_0001.ptau")

    # 1) Initialisation
    _run(f"snarkjs powersoftau new bn128 {power} {pot0} -v", cwd=workdir)

    # 2) Contribution (snarkjs 0.7.5 lit nom + entropie sur stdin; pas d'options --name/-e/-v)
    #    Ordre attendu: "Enter a name" puis "Entropy"
    _run(
        f"snarkjs powersoftau contribute {pot0} {pot1}",
        cwd=workdir,
        stdin="first contribution\nrandom_entropy\n",
    )

    # 3) Passage phase 2
    _run(f"snarkjs powersoftau prepare phase2 {pot1} {ptau_path}", cwd=workdir)


# -------------------------------
# Export des inputs par chunk (à partir de clients.json/avg.json)
# -------------------------------
def export_inputs_for_round(
    round_dir: str,
    scale: int = DEFAULT_SCALE,
    chunk: int = DEFAULT_CHUNK,
) -> int:
    """
    Lit clients.json et avg.json dans round_dir, et produit inputs/input_chunk_*.json avec padding.
    Retourne le nombre de chunks générés.
    """
    clients_path = os.path.join(round_dir, "clients.json")
    avg_path     = os.path.join(round_dir, "avg.json")
    if not (os.path.exists(clients_path) and os.path.exists(avg_path)):
        raise RuntimeError(f"Manque clients.json/avg.json dans {round_dir}")

    with open(clients_path) as f:
        clients = json.load(f)["clients"]
    with open(avg_path) as f:
        avg = json.load(f)["avg"]

    if len(clients) != 2:
        raise RuntimeError(f"[ZKP] Attendu 2 clients, trouvé {len(clients)}")

    w1 = clients[0]["flat_weights"]
    w2 = clients[1]["flat_weights"]
    if not (len(w1) == len(w2) == len(avg)):
        raise RuntimeError("[ZKP] Tailles incohérentes (w1/w2/avg)")

    # Quantification + moyenne publique (floor via //2)
    W1 = [_q(v, scale) for v in w1]
    W2 = [_q(v, scale) for v in w2]
    AVG_pub = [(a + b) // 2 for a, b in zip(W1, W2)]

    inputs_dir = os.path.join(round_dir, "inputs")
    os.makedirs(inputs_dir, exist_ok=True)

    L = len(W1)
    n_chunks = math.ceil(L / chunk)
    for k in range(n_chunks):
        a, b = k * chunk, min((k + 1) * chunk, L)
        pad = chunk - (b - a)
        payload = {
            "w1":        W1[a:b] + [0] * pad,
            "w2":        W2[a:b] + [0] * pad,
            "w_avg_pub": AVG_pub[a:b] + [0] * pad,
        }
        with open(os.path.join(inputs_dir, f"input_chunk_{k}.json"), "w") as f:
            json.dump(payload, f)

    # Meta utile au debug
    with open(os.path.join(round_dir, "meta.json"), "w") as f:
        json.dump(
            {"scale": scale, "chunk": chunk, "length": L, "n_chunks": n_chunks},
            f,
            indent=2,
        )

    return n_chunks


# -------------------------------
# Build circuit + setup Groth16 si besoin
# -------------------------------
def _ensure_circuit_built(
    circuit_dir: str = CIRCUIT_DIR,
    ptau_path: str = PTAU_PATH,
) -> None:
    """
    Compile le circuit si nécessaire, réalise le setup Groth16 si besoin,
    et exporte la verification key. Appelle _ensure_ptau() avant le setup.
    """
    wasm = os.path.join(circuit_dir, "avg2_chunk_js", "avg2_chunk.wasm")
    r1cs = os.path.join(circuit_dir, "avg2_chunk.r1cs")
    zkey = os.path.join(circuit_dir, "avg2_chunk_final.zkey")
    vkey = os.path.join(circuit_dir, "verification_key.json")
    circom_file = os.path.join(circuit_dir, "avg2_chunk.circom")

    if not os.path.exists(circom_file):
        raise RuntimeError(f"[ZKP] Circuit introuvable: {circom_file}")

    # S'assurer que le ptau est prêt (le générer si autorisé)
    _ensure_ptau(ptau_path)

    # Compiler si wasm/r1cs manquent
    if not (os.path.exists(wasm) and os.path.exists(r1cs)):
        _run(f"circom {circom_file} --r1cs --wasm --sym -l /app/node_modules -o {circuit_dir}")

    # Setup Groth16 + vkey si besoin
    if not os.path.exists(zkey):
        _run(f"snarkjs groth16 setup {r1cs} {ptau_path} {zkey}")
    if not os.path.exists(vkey):
        _run(f"snarkjs zkey export verificationkey {zkey} {vkey}")


# -------------------------------
# Prover/Vérifier par chunk pour un round
# -------------------------------
def prove_round_chunks(
    round_dir: str,
    circuit_dir: str = CIRCUIT_DIR,
    ptau_path: str = PTAU_PATH,
) -> int:
    _ensure_circuit_built(circuit_dir, ptau_path)

    wasm = os.path.join(circuit_dir, "avg2_chunk_js", "avg2_chunk.wasm")
    genw = os.path.join(circuit_dir, "avg2_chunk_js", "generate_witness.js")
    zkey = os.path.join(circuit_dir, "avg2_chunk_final.zkey")
    vkey = os.path.join(circuit_dir, "verification_key.json")

    # NOUVEAU: on lit inputs commités (avec merkle) + on injecte roots
    round_name = os.path.basename(os.path.normpath(round_dir))
    commits_dir = os.path.join("/app/commits", round_name)
    inputs_dir  = os.path.join(commits_dir, "inputs")

    roots_path = os.path.join(commits_dir, "roots.json")
    with open(roots_path) as f:
        roots = json.load(f)
    root_w1 = int(roots["root_w1"])
    root_w2 = int(roots["root_w2"])

    input_files = sorted(glob.glob(os.path.join(inputs_dir, "input_chunk_*.json")))
    if not input_files:
        raise RuntimeError(f"[ZKP] Aucun input_chunk_*.json dans {inputs_dir}")

    done = 0
    for inp in input_files:
        k = os.path.splitext(os.path.basename(inp))[0].split("_")[-1]
        wtns = os.path.join(round_dir, f"witness_{k}.wtns")
        proof = os.path.join(round_dir, f"proof_{k}.json")
        publ  = os.path.join(round_dir, f"public_{k}.json")

        # Charger l'input enrichi et injecter les roots publiques
        with open(inp) as f:
            payload = json.load(f)
        payload["root_w1"] = root_w1
        payload["root_w2"] = root_w2
        # chunkIndex est déjà dedans (ajouté lors du commit); sinon:
        # payload.setdefault("chunkIndex", int(k))

        # Écrire un input temporaire à passer au witness
        tmp_inp = os.path.join(round_dir, f"_inp_{k}.json")
        with open(tmp_inp, "w") as f:
            json.dump(payload, f)

        _run(f"node {genw} {wasm} {tmp_inp} {wtns}")
        _run(f"snarkjs groth16 prove {zkey} {wtns} {proof} {publ}")
        _run(f"snarkjs groth16 verify {vkey} {publ} {proof}")

        os.remove(tmp_inp)
        done += 1

    return done



# -------------------------------
# Point d'entrée unique: export + (optionnel) prove/verify
# -------------------------------
def export_and_maybe_prove(round_dir: str) -> None:
    """
    Exporte les inputs en chunks à partir de clients.json/avg.json.
    Si ZKP_AUTOPROVE=1, enchaîne sur witness → prove → verify.
    """
    n = export_inputs_for_round(round_dir, DEFAULT_SCALE, DEFAULT_CHUNK)
    on_round_proved(round_dir)
    if AUTOPROVE:
        c = prove_round_chunks(round_dir, CIRCUIT_DIR, PTAU_PATH)
        print(f"[ZKP] Round {os.path.basename(round_dir)} : {c}/{n} chunks prouvés et vérifiés.")
    else:
        print(f"[ZKP] Round {os.path.basename(round_dir)} : {n} chunks exportés (AUTO_PROVE désactivé).")





def on_round_proved(round_dir: str, commits_root: str = "/app/commits"):
    out_dir = integrate_commitments_for_round(round_dir, commits_root=commits_root)
    print(f"[Commitments] {os.path.basename(os.path.normpath(round_dir))} -> {out_dir}")
