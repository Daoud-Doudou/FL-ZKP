from __future__ import annotations
import os, json, math
from typing import List, Tuple
from utils.poseidon_wrapper import poseidon_hash_array
from utils.merkle import build_merkle, get_merkle_proof
import shutil

DEFAULT_SCALE = 1_000_000
DEFAULT_CHUNK = 4096

def _q(x: float, scale: int = DEFAULT_SCALE) -> int:
    # quantification arrondi au plus proche
    return int(round(x * scale))

def _pad_right(xs: List[int], size: int) -> List[int]:
    if len(xs) >= size:
        return xs[:size]
    return xs + [0] * (size - len(xs))

def _chunkify(xs: List[int], chunk: int) -> List[List[int]]:
    out = []
    L = len(xs)
    n_chunks = math.ceil(L / chunk) if L > 0 else 1
    for k in range(n_chunks):
        a = k * chunk
        b = min((k + 1) * chunk, L)
        out.append(_pad_right(xs[a:b], chunk))
    return out

def _hash_chunk_poseidon(arr4096: List[int]) -> int:
    # Convention : Poseidon sur toute la liste (arité variable) pour compatibilité circomlibjs
    # arr4096 doit être exactement de taille CHUNK (paddé si besoin)
    return poseidon_hash_array(arr4096)

def _load_round_inputs(round_dir: str) -> Tuple[List[float], List[float], List[float]]:
    clients_path = os.path.join(round_dir, "clients.json")
    avg_path     = os.path.join(round_dir, "avg.json")

    if not (os.path.exists(clients_path) and os.path.exists(avg_path)):
        # 🔍 DEBUG : état exact du dossier au moment où on ne trouve pas les fichiers
        try:
            listing = sorted(os.listdir(round_dir))[:20]
        except Exception as e:
            listing = [f"<ls error: {e}>"]
        raise RuntimeError(
            f"Manque clients.json/avg.json dans {round_dir} | "
            f"exists(clients)={os.path.exists(clients_path)} "
            f"exists(avg)={os.path.exists(avg_path)} | ls={listing}"
        )

    with open(clients_path) as f:
        clients = json.load(f)["clients"]
    with open(avg_path) as f:
        avg = json.load(f)["avg"]

    if len(clients) != 2:
        raise RuntimeError(f"Attendu 2 clients, trouvé {len(clients)}")

    w1 = clients[0]["flat_weights"]
    w2 = clients[1]["flat_weights"]
    if not (len(w1) == len(w2) == len(avg)):
        raise RuntimeError("Tailles incohérentes (w1/w2/avg)")

    return w1, w2, avg

def build_commitments_for_round(
    round_dir: str,
    scale: int = DEFAULT_SCALE,
    chunk: int = DEFAULT_CHUNK,
    output_dir: str | None = None,   # <-- nouveau paramètre
) -> None:
    """
    1) Charge w1/w2/avg depuis round_dir (clients.json / avg.json)
    2) Quantifie et découpe w1/w2 en chunks de `chunk` éléments (padding à droite)
    3) Calcule les feuilles: Poseidon-fold du chunk (acc=1; acc=Poseidon([acc,x]))
    4) Construit 2 arbres Merkle (w1 et w2)
    5) Écrit roots.json dans output_dir (ou round_dir si non fourni)
    6) Enrichit chaque input_chunk_k.json dans output_dir/inputs
       avec chunkIndex, siblings/pathBits pour w1 et w2
    """
    # 1) Lire les poids
    w1_f, w2_f, avg_f = _load_round_inputs(round_dir)

    # 2) Quantifier
    W1 = [_q(x, scale) for x in w1_f]
    W2 = [_q(x, scale) for x in w2_f]

    # 3) Découper en chunks (padding)
    W1_chunks = _chunkify(W1, chunk)
    W2_chunks = _chunkify(W2, chunk)
    assert len(W1_chunks) == len(W2_chunks)
    n_chunks = len(W1_chunks)

    # 4) Feuilles (hash des chunks, poseidon fold)
    leaves1 = [_hash_chunk_poseidon(c) for c in W1_chunks]
    leaves2 = [_hash_chunk_poseidon(c) for c in W2_chunks]

    # 5) Arbres Merkle et racines
    root1, tree1, depth1 = build_merkle(leaves1)
    root2, tree2, depth2 = build_merkle(leaves2)
    if depth1 != depth2:
        raise RuntimeError(f"Profondeurs Merkle différentes: {depth1} vs {depth2}")

    # Dossiers in/out
    out_dir = output_dir or round_dir
    os.makedirs(out_dir, exist_ok=True)

    # 6) Écrire roots.json dans out_dir
    roots_path = os.path.join(out_dir, "roots.json")
    with open(roots_path, "w") as f:
        json.dump(
            {
                "root_w1": str(root1),
                "root_w2": str(root2),
                "depth": int(depth1),
                "n_chunks": int(n_chunks),
                "chunk_size": int(chunk),
                "scale": int(scale),
            },
            f,
            indent=2,
        )

    # 7) Enrichir inputs : lecture depuis round_dir/inputs, écriture dans out_dir/inputs
    in_inputs_dir  = os.path.join(round_dir, "inputs")
    out_inputs_dir = os.path.join(out_dir,  "inputs")
    os.makedirs(out_inputs_dir, exist_ok=True)

    for k in range(n_chunks):
        inp_path = os.path.join(in_inputs_dir,  f"input_chunk_{k}.json")
        out_path = os.path.join(out_inputs_dir, f"input_chunk_{k}.json")
        if not os.path.exists(inp_path):
            # si l'input n'existe pas (cas rare), on saute
            continue

        sib1, bits1 = get_merkle_proof(tree1, k)
        sib2, bits2 = get_merkle_proof(tree2, k)

        with open(inp_path) as f:
            payload = json.load(f)

        payload.update(
            {
                "chunkIndex": k,
                "siblings1": [str(x) for x in sib1],
                "pathBits1": [int(b) for b in bits1],
                "siblings2": [str(x) for x in sib2],
                "pathBits2": [int(b) for b in bits2],
            }
        )

        with open(out_path, "w") as f:
            json.dump(payload, f)
