pragma circom 2.1.6;

template Avg2Chunk(CHUNK) {
    signal input w1[CHUNK];         // privés
    signal input w2[CHUNK];         // privés
    signal input w_avg_pub[CHUNK];  // publics
    signal r[CHUNK];                // privés

    for (var i=0; i<CHUNK; i++) {
        r[i] <== w1[i] + w2[i] - 2*w_avg_pub[i];
        r[i] * (r[i] - 1) === 0;  // r ∈ {0,1}
    }
}
component main { public [w_avg_pub] } = Avg2Chunk(4096);  // <- 4096 !
