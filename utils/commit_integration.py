# utils/commit_integration.py
from __future__ import annotations
import os, shutil, json
from utils.commitment import build_commitments_for_round, DEFAULT_SCALE, DEFAULT_CHUNK

def _swap_atomically(src_tmp: str, dst_final: str):
    if os.path.exists(dst_final):
        shutil.rmtree(dst_final)
    os.replace(src_tmp, dst_final)

def integrate_commitments_for_round(round_dir: str, commits_root: str = "/app/commits") -> str:
    """
    Génère Poseidon+Merkle pour UN round, écrit atomiquement dans /app/commits/<round>/.
    round_dir: ex. /app/shared-data/zkp/round1
    """
    round_name = os.path.basename(os.path.normpath(round_dir))
    final_out  = os.path.join(commits_root, round_name)
    tmp_out    = final_out + ".tmp"

    # 1) dossier temp propre
    if os.path.exists(tmp_out):
        shutil.rmtree(tmp_out)
    os.makedirs(tmp_out, exist_ok=True)

    # 2) engagements
    build_commitments_for_round(round_dir=round_dir, output_dir=tmp_out)

    # 3) petit statut
    status = {
        "round_dir": os.path.abspath(round_dir),
        "params": {"scale": int(DEFAULT_SCALE), "chunk": int(DEFAULT_CHUNK)},
        "commitments": "OK"
    }
    with open(os.path.join(tmp_out, "status.json"), "w") as f:
        json.dump(status, f, indent=2)

    # 4) swap atomique
    _swap_atomically(tmp_out, final_out)
    return final_out
