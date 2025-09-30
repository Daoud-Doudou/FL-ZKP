# tools/commit_round.py
import sys, os, shutil, json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.commitment import build_commitments_for_round, DEFAULT_SCALE, DEFAULT_CHUNK


def _ensure_clean_dir(p: str):
    if os.path.exists(p):
        shutil.rmtree(p)
    os.makedirs(p, exist_ok=True)

def _atomic_replace(tmp_dir: str, final_dir: str):
    # Remplace d’un coup pour éviter des dossiers “à moitié écrits”
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    os.replace(tmp_dir, final_dir)

def main():
    # Usage: python3 tools/commit_round.py /path/to/round_dir [ /path/to/commits_root ] [--skip-if-exists]
    if len(sys.argv) < 2:
        print("Usage: python3 tools/commit_round.py /path/to/round_dir [ /path/to/commits_root ] [--skip-if-exists]")
        sys.exit(1)

    round_dir = sys.argv[1]
    commits_root = None
    skip_if_exists = False

    for arg in sys.argv[2:]:
        if arg == "--skip-if-exists":
            skip_if_exists = True
        elif commits_root is None:
            commits_root = arg
        else:
            print("Trop d’arguments. Usage: python3 tools/commit_round.py /path/to/round_dir [ /path/to/commits_root ] [--skip-if-exists]")
            sys.exit(1)

    if commits_root is None:
        # par défaut, “commits” à côté de shared-data/zkp/
        commits_root = os.path.join(os.path.dirname(os.path.dirname(round_dir)), "commits")

    round_name = os.path.basename(os.path.normpath(round_dir))
    final_out = os.path.join(commits_root, round_name)
    tmp_out = final_out + ".tmp"

    if skip_if_exists and os.path.exists(final_out):
        print(f"   SKIP: {final_out} existe déjà (flag --skip-if-exists)")
        return

    print(f"   Build -> {final_out}")
    _ensure_clean_dir(tmp_out)

    # 1) Commitments (roots.json + inputs enrichis) dans le dossier temporaire
    build_commitments_for_round(round_dir=round_dir, output_dir=tmp_out)

    # 2) Petit statut lisible
    status = {
        "round_dir": os.path.abspath(round_dir),
        "params": {"scale": int(DEFAULT_SCALE), "chunk": int(DEFAULT_CHUNK)},
        "status": "OK"
    }
    with open(os.path.join(tmp_out, "status.json"), "w") as f:
        json.dump(status, f, indent=2)

    # 3) (Hook futur) — ZKP
    # Ici tu brancheras ton pipeline Circom/snarkjs (génération et vérification),
    # et tu écriras les artefacts dans tmp_out/proof/...
    # Ex:
    # os.makedirs(os.path.join(tmp_out, "proof"), exist_ok=True)
    # ... run circom/snarkjs ...
    # ... écrire proof.json, public.json, verification_key.json ...

    # 4) Échange atomique tmp -> final
    _atomic_replace(tmp_out, final_out)
    print(f"   OK: {final_out} (écrit atomiquement)")

if __name__ == "__main__":
    main()

