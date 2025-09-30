from typing import List, Tuple
from utils.poseidon_wrapper import poseidon_hash_array

def build_merkle(leaves: List[int]) -> Tuple[int, List[List[int]], int]:
    """
    Construit un arbre de Merkle binaire avec Poseidon.
    - leaves : liste des feuilles (int déjà hashés, ex: hash de chaque chunk)
    - return : (root, tree, depth)
      * root : racine Merkle (int)
      * tree : liste de niveaux [level0, level1, ...] (level0=feuilles)
      * depth : hauteur de l'arbre (nb de niveaux - 1)
    """
    if len(leaves) == 0:
        raise ValueError("Pas de feuilles pour construire un arbre Merkle")

    # Pad à la puissance de 2 la plus proche
    n = 1
    while n < len(leaves):
        n *= 2
    padded = leaves + [0] * (n - len(leaves))  # padding avec 0

    tree = [padded]
    cur = padded
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur), 2):
            left, right = cur[i], cur[i+1]
            nxt.append(poseidon_hash_array([left, right]))
        tree.append(nxt)
        cur = nxt

    root = tree[-1][0]
    depth = len(tree) - 1
    return root, tree, depth

def get_merkle_proof(tree: List[List[int]], index: int) -> Tuple[List[int], List[int]]:
    """
    Retourne la preuve Merkle pour la feuille à 'index'.
    - tree : liste de niveaux retournée par build_merkle
    - index : index de la feuille originale
    - return : (siblings, pathBits)
      * siblings : liste des frères (int)
      * pathBits : 0 si feuille à gauche, 1 si feuille à droite
    """
    siblings, pathBits = [], []
    cur_index = index
    for level in range(len(tree) - 1):  # jusqu'à l'avant-dernier niveau
        level_nodes = tree[level]
        is_right = cur_index % 2
        sibling_index = cur_index - 1 if is_right else cur_index + 1
        sibling_val = level_nodes[sibling_index] if sibling_index < len(level_nodes) else 0

        siblings.append(sibling_val)
        pathBits.append(is_right)
        cur_index //= 2
    return siblings, pathBits
