"""Fetch every English printing of a Pokémon from the Pokémon TCG API and prepare binder data.

Usage:
  python fetch_cards.py "Articuno" --out <binder dir>
  python fetch_cards.py "Mew" --out <dir> --exact            # only cards named exactly "Mew" (plus "Mew ex", "Mew V", ...)
  python fetch_cards.py "Mew" --out <dir> --exclude "Mewtwo,Mewtwo ex"
  python fetch_cards.py "Pikachu" --out <dir> --query 'name:"pikachu*"'   # raw API query

Writes to <dir>:
  cards.json      raw API response (all cards)
  data.json       compact binder data, one entry per printing with its finishes ("v")
  imgurls.json    {card id: [small url, large url]} for the Google-hosted page
  meta.json       name, slug, dex number, species category, main TCG type
  cards/*.webp    440px images for the Claude artifact
  small/*.webp    340px images for the single-file version
Re-run after editing <dir>/overrides.json to apply finish corrections (images are cached).
"""
import argparse, json, os, re, sys, urllib.parse, urllib.request, concurrent.futures as cf
from collections import Counter

API = "https://api.pokemontcg.io/v2/cards"
ORDER = ["1stEdition", "unlimited", "normal", "1stEditionHolofoil", "unlimitedHolofoil", "holofoil", "reverseHolofoil"]
HOLO_HINTS = ("holo", "ex", "gx", "v", "vmax", "vstar", "ultra", "secret", "illustration", "rainbow", "shiny", "radiant", "amazing", "prism", "legend", "break", "hyper", "promo", "ace spec")


def get_json(url, tries=4):
    """The Pokémon TCG API sometimes answers 500/504; wait and retry."""
    import time
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 pokemon-binder"})
            return json.load(urllib.request.urlopen(req, timeout=90))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def fetch_all(q):
    cards, page = [], 1
    while True:
        url = f"{API}?q={urllib.parse.quote(q)}&pageSize=250&page={page}&orderBy=set.releaseDate,number"
        d = get_json(url)
        cards += d["data"]
        if len(cards) >= d.get("totalCount", 0) or not d["data"]:
            return cards
        page += 1


def infer_variants(c):
    """Finishes from TCGplayer price keys; when there are none, guess from rarity and flag it."""
    v = list((c.get("tcgplayer") or {}).get("prices", {}).keys())
    if v:
        return sorted(set(v) & set(ORDER), key=ORDER.index), False
    r = (c.get("rarity") or "").lower()
    words = set(re.split(r"[\s-]+", r)) | set(re.split(r"[\s-]+", c["name"].lower()))
    if "double rare" in r or any(h in words if len(h) <= 5 else h in r for h in HOLO_HINTS):
        return ["holofoil"], True
    return ["normal", "reverseHolofoil"], True


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def species_info(name):
    slug = slugify(name.replace("♀", "-f").replace("♂", "-m").replace(".", "").replace("'", ""))
    try:
        sp = get_json(f"https://pokeapi.co/api/v2/pokemon-species/{slug}")
        genus = next((g["genus"] for g in sp["genera"] if g["language"]["name"] == "en"), "")
        return sp["id"], genus
    except Exception:
        return None, ""


def save_images(cards, out):
    from PIL import Image
    os.makedirs(f"{out}/raw", exist_ok=True); os.makedirs(f"{out}/cards", exist_ok=True); os.makedirs(f"{out}/small", exist_ok=True)

    def one(c):
        raw = f"{out}/raw/{c['id']}.png"
        if not os.path.exists(raw):
            for key in ("large", "small"):
                try:
                    req = urllib.request.Request(c["images"][key], headers={"User-Agent": "Mozilla/5.0"})
                    open(raw, "wb").write(urllib.request.urlopen(req, timeout=90).read())
                    break
                except Exception:
                    continue
            else:
                return c["id"], "FAILED"
        im = Image.open(raw).convert("RGBA")
        for folder, w, q in (("cards", 440, 80), ("small", 340, 74)):
            dst = f"{out}/{folder}/{c['id']}.webp"
            if not os.path.exists(dst):
                im.resize((w, round(im.height * w / im.width)), Image.LANCZOS).save(dst, "WEBP", quality=q, method=4)
        return c["id"], "ok"

    with cf.ThreadPoolExecutor(12) as ex:
        failed = [cid for cid, status in ex.map(one, cards) if status != "ok"]
    return failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pokemon")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exact", action="store_true", help="names that start with the Pokémon's name as a word, plus prefixed forms like Galarian X, Dark X, X's")
    ap.add_argument("--exclude", default="", help="comma-separated card names to drop")
    ap.add_argument("--query", help="raw Pokémon TCG API q= string")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()
    out = a.out
    os.makedirs(out, exist_ok=True)

    raw_path = f"{out}/cards.json"
    if os.path.exists(raw_path) and not a.query:
        cards = json.load(open(raw_path, encoding="utf-8"))
    else:
        cards = fetch_all(a.query or f'name:"*{a.pokemon.lower()}*"')
        json.dump(cards, open(raw_path, "w", encoding="utf-8"), ensure_ascii=False)

    name_l = a.pokemon.lower()
    if a.exact:
        word = re.compile(r"(^|[\s'’&-])" + re.escape(name_l) + r"($|[\s'’&-])")
        cards = [c for c in cards if word.search(c["name"].lower())]
    excl = {x.strip().lower() for x in a.exclude.split(",") if x.strip()}
    cards = [c for c in cards if c["name"].lower() not in excl]

    ov_path = f"{out}/overrides.json"
    ov = json.load(open(ov_path, encoding="utf-8")) if os.path.exists(ov_path) else {}
    drop = set(ov.get("exclude_ids", []))
    cards = [c for c in cards if c["id"] not in drop]
    cards.sort(key=lambda c: (c["set"]["releaseDate"], c["set"]["id"], c["number"].zfill(6)))

    data, guessed = [], []
    for c in cards:
        v, inferred = infer_variants(c)
        if c["id"] in ov.get("variants", {}):
            v, inferred = sorted(ov["variants"][c["id"]], key=ORDER.index), False
        if inferred:
            guessed.append(c["id"])
        data.append({"id": c["id"], "name": c["name"], "set": c["set"]["name"], "series": c["set"]["series"],
                     "date": c["set"]["releaseDate"], "num": c["number"], "total": c["set"].get("printedTotal", ""),
                     "rarity": c.get("rarity", ""), "v": v})
    json.dump(data, open(f"{out}/data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump({c["id"]: [c["images"]["small"], c["images"]["large"]] for c in cards}, open(f"{out}/imgurls.json", "w"), separators=(",", ":"))

    types = Counter(t for c in cards for t in (c.get("types") or []))
    dex, genus = species_info(a.pokemon)
    meta = {"pokemon": a.pokemon, "slug": slugify(a.pokemon), "dex": dex, "genus": genus,
            "type": types.most_common(1)[0][0] if types else "Colorless"}
    json.dump(meta, open(f"{out}/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    failed = [] if a.no_images else save_images(cards, out)

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(data)} printings, {sum(len(d['v']) for d in data)} pockets | type {meta['type']} | dex {dex} {genus}")
    print("Distinct card names:", ", ".join(sorted({d['name'] for d in data})))
    print("\nid | name | set | date | number | rarity | finishes")
    for d in data:
        flag = "  <-- GUESSED, check" if d["id"] in guessed else ""
        print(f"{d['id']} | {d['name']} | {d['set']} | {d['date']} | {d['num']}/{d['total']} | {d['rarity']} | {', '.join(d['v'])}{flag}")
    if failed:
        print("\nImage downloads failed for:", ", ".join(failed))


if __name__ == "__main__":
    main()
