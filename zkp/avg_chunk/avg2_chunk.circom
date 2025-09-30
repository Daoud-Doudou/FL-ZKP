pragma circom 2.1.6;

include "circomlib/circuits/poseidon.circom";

// Hash fold: acc = 1; for x in arr: acc = Poseidon([acc, x])
template HashChunk(CHUNK) {
    signal input arr[CHUNK];   // privés (field elements)
    signal output out;         // leaf

    component h[CHUNK];
    signal accs[CHUNK + 1];
    accs[0] <== 1;

    for (var i = 0; i < CHUNK; i++) {
        h[i] = Poseidon(2);
        h[i].inputs[0] <== accs[i];
        h[i].inputs[1] <== arr[i];
        accs[i + 1] <== h[i].out;
    }
    out <== accs[CHUNK];
}

// Vérif Merkle (Poseidon arité 2), path privé
// pathBits[i] ∈ {0,1}: 0 = (cur,sib), 1 = (sib,cur)
template MerkleVerify(DEPTH) {
    signal input leaf;                  // privé
    signal input root_pub;              // PUBLIC
    signal input siblings[DEPTH];       // privé
    signal input pathBits[DEPTH];       // privé

    // états intermédiaires
    signal cur[DEPTH + 1];
    signal left[DEPTH];
    signal right[DEPTH];

    // PRÉ-DÉCLARATION (pas dans la boucle)
    component h[DEPTH];
    signal deltaL[DEPTH];
    signal tmpL[DEPTH];
    signal deltaR[DEPTH];
    signal tmpR[DEPTH];

    // départ
    cur[0] <== leaf;

    for (var i = 0; i < DEPTH; i++) {
        // bit ∈ {0,1}
        pathBits[i] * (pathBits[i] - 1) === 0;

        // left = cur + b*(sib - cur)
        deltaL[i] <== siblings[i] - cur[i];
        tmpL[i]   <== deltaL[i] * pathBits[i];
        left[i]   <== cur[i] + tmpL[i];

        // right = sib + b*(cur - sib)
        deltaR[i] <== cur[i] - siblings[i];
        tmpR[i]   <== deltaR[i] * pathBits[i];
        right[i]  <== siblings[i] + tmpR[i];

        // hash
        h[i] = Poseidon(2);
        h[i].inputs[0] <== left[i];
        h[i].inputs[1] <== right[i];

        cur[i + 1] <== h[i].out;
    }

    // égalité à la racine publique
    cur[DEPTH] === root_pub;
}

// Avg + Commitments par chunk
template Avg2ChunkCommit(CHUNK, DEPTH) {
    // --- Données avg ---
    signal input w1[CHUNK];            // privés
    signal input w2[CHUNK];            // privés
    signal input w_avg_pub[CHUNK];     // PUBLICS

    // --- Engagements (public roots + index; merkle path privé) ---
    signal input root_w1;              // PUBLIC
    signal input root_w2;              // PUBLIC
    signal input chunkIndex;           // PUBLIC (utile dans les publics)
    signal input siblings1[DEPTH];     // privés
    signal input pathBits1[DEPTH];     // privés
    signal input siblings2[DEPTH];     // privés
    signal input pathBits2[DEPTH];     // privés

    // 1) Contrainte moyenne (comme avant)
    signal r[CHUNK];
    for (var i = 0; i < CHUNK; i++) {
        r[i] <== w1[i] + w2[i] - 2 * w_avg_pub[i];
        r[i] * (r[i] - 1) === 0;  // r ∈ {0,1}
    }

    // 2) Hash fold des chunks
    component hw1 = HashChunk(CHUNK);
    component hw2 = HashChunk(CHUNK);
    for (var j = 0; j < CHUNK; j++) {
        hw1.arr[j] <== w1[j];
        hw2.arr[j] <== w2[j];
    }

    // 3) Vérifs Merkle jusqu'aux racines publiques
    component mv1 = MerkleVerify(DEPTH);
    mv1.leaf <== hw1.out;
    mv1.root_pub <== root_w1;
    for (var k = 0; k < DEPTH; k++) {
        mv1.siblings[k] <== siblings1[k];
        mv1.pathBits[k]  <== pathBits1[k];
    }

    component mv2 = MerkleVerify(DEPTH);
    mv2.leaf <== hw2.out;
    mv2.root_pub <== root_w2;
    for (var t = 0; t < DEPTH; t++) {
        mv2.siblings[t] <== siblings2[t];
        mv2.pathBits[t]  <== pathBits2[t];
    }
}


component main { public [w_avg_pub, root_w1, root_w2, chunkIndex] } = Avg2ChunkCommit(4096, 6);
