// zkp/poseidon_hash.js
// Usage :
//   node zkp/poseidon_hash.js '[1,2,3]'           // ok tableaux courts
//   echo '[1,2,3]' | node zkp/poseidon_hash.js
//
// Conventions :
// - Si la longueur == 2  -> appel direct poseidon([a,b]) (hash de nœud Merkle)
// - Sinon (longueur != 2)-> pliage : acc=1 ; pour x : acc = poseidon([acc, x])
// - Tous les entiers sont réduits modulo p (support des négatifs)

function parseInput(str) {
  const s = (str || "").trim();
  if (!s) return null;
  const arr = JSON.parse(s);
  if (!Array.isArray(arr)) throw new Error("Input must be a JSON array");
  return arr.map((x) => BigInt(x));
}

async function readFromStdin() {
  return new Promise((resolve) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolve(data));
  });
}

async function main() {

  const { buildPoseidon } = await import("circomlibjs");
  
  let inputJson = !process.stdin.isTTY ? await readFromStdin() : "";
  if (!inputJson || inputJson.trim() === "") inputJson = process.argv[2] || "";

  if (!inputJson || inputJson.trim() === "") {
    console.error("Usage: echo '[1,2,3]' | node zkp/poseidon_hash.js");
    console.error("   or: node zkp/poseidon_hash.js '[1,2,3]'");
    process.exit(1);
  }

  const poseidon = await buildPoseidon();
  const F = poseidon.F;
  const p = F.p;

  // normalise les entiers (support des négatifs)
  const raw = parseInput(inputJson);
  const arr = raw.map((x) => ((x % p) + p) % p);

  let out;
  if (arr.length === 2) {
    // cas "nœud Merkle" : hash direct de 2 éléments
    out = poseidon(arr);
  } else {
    // cas "feuille chunk" (ou tailles ≠ 2) : pliage à arité 2 avec acc=1
    let acc = 1n;
    for (const x of arr) {
      acc = poseidon([acc, x]);
    }
    out = acc;
  }

  process.stdout.write(F.toString(out) + "\n");
}

main().catch((e) => {
  console.error("[poseidon_hash] Error:", e.message || e);
  process.exit(1);
});
