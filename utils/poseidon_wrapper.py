import subprocess
import json
from typing import List

def poseidon_hash_array(arr: List[int]) -> int:
    """
    Calcule Poseidon(arr) en appelant le script Node.
    - arr : liste d'entiers (déjà quantifiés si ce sont des poids)
    - return : int (élément du champ BN254 en base 10)
    """
    if not isinstance(arr, list):
        raise TypeError("poseidon_hash_array attend une liste d'entiers")
    # Sécurité basique : s'assurer que tous les éléments sont des int
    for i, x in enumerate(arr):
        if not isinstance(x, int):
            raise TypeError(f"arr[{i}] n'est pas un int (reçu: {type(x)})")

    payload = json.dumps(arr)
    try:
        # Appel en passant le JSON en argument (plus simple/robuste que stdin)
        res = subprocess.run(
            ["node", "zkp/poseidon_hash.js", payload],
            check=True,
            capture_output=True,
            text=True,
        )
        out = res.stdout.strip()
        return int(out)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Erreur Poseidon (Node): {e.stderr or e.stdout}")
