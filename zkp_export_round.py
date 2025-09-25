# zkp_export_round.py
import json, os, sys, math

SCALE = 1_000_000
CHUNK = 4096

def q(x): return int(round(x*SCALE))

def main():
    try:
        r = int(sys.argv[1])
    except:
        print("Usage: python zkp_export_round.py <round_id>")
        sys.exit(1)

    base = f"shared-data/zkp/round{r}"
    with open(os.path.join(base, "clients.json")) as f:
        clients = json.load(f)["clients"]
    with open(os.path.join(base, "avg.json")) as f:
        avg = json.load(f)["avg"]

    # sécurité: exactement 2 clients
    if len(clients) != 2:
        raise RuntimeError(f"Attendu 2 clients, trouvé {len(clients)}")

    w1 = clients[0]["flat_weights"]
    w2 = clients[1]["flat_weights"]
    if len(w1) != len(w2) or len(w1) != len(avg):
        raise RuntimeError("Taille incohérente")

    # quantification
    W1 = [q(v) for v in w1]
    W2 = [q(v) for v in w2]
    AVG = [q(v) for v in avg]

    # moyenne "floor" côté public (défense en profondeur)
    AVG_pub = [(a+b)//2 for a,b in zip(W1,W2)]

    # sanity: r in {0,1}
    bad = [i for i,(a,b,m) in enumerate(zip(W1,W2,AVG_pub)) if (a+b-2*m) not in (0,1)]
    if bad:
        print(f"[WARN] reste hors {{0,1}} sur {len(bad)} indices (OK si numériquement bord), on continue...")

    out_dir = os.path.join(base, "inputs")
    os.makedirs(out_dir, exist_ok=True)

    L = len(W1)
    n_chunks = math.ceil(L/CHUNK)
    for k in range(n_chunks):
        a = k*CHUNK; b = min((k+1)*CHUNK, L)
        # padding à droite si dernier chunk plus court
        pad = CHUNK - (b-a)
        payload = {
            "w1":       W1[a:b] + [0]*pad,
            "w2":       W2[a:b] + [0]*pad,
            "w_avg_pub":AVG_pub[a:b] + [0]*pad
        }
        with open(os.path.join(out_dir, f"input_chunk_{k}.json"), "w") as f:
            json.dump(payload, f)
    print(f"Export round {r} -> {n_chunks} chunks dans {out_dir}")

if __name__ == "__main__":
    main()
