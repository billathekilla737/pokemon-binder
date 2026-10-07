"""Build a Pokémon binder from a folder prepared by fetch_cards.py.

Usage:
  python build.py <binder dir> artifact                 -> <dir>/artifact/index.html (+ cards/*.webp) for a Claude artifact
  python build.py <binder dir> sheet [--sync-url URL]   -> <dir>/sheet/Binder.html + Code.gs.txt for a Google Sheet web app
  python build.py <binder dir> file  [--sync-url URL]   -> <dir>/<Title>.html, one self-contained file (images inside)

The sheet target is the one that works on every phone (iPhone included) and syncs between people.
"""
import argparse, base64, json, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "templates")

# Binder cover and accent colors per TCG type: light (cover, cover-hi, accent, accent-soft), dark (same order)
THEMES = {
    "Water":     (("#1d3a56", "#2a5075", "#1f7fb6", "#d5eaf6"), ("#0c2136", "#163452", "#6cc3ee", "#13334a")),
    "Fire":      (("#5a2216", "#7a3420", "#b8481a", "#fbe1d4"), ("#2a0f0a", "#45190f", "#ff9a66", "#3d1a10")),
    "Grass":     (("#1f4a2b", "#2d6640", "#2a7f44", "#d9f0de"), ("#0d2414", "#183a22", "#6fd38d", "#163a22")),
    "Lightning": (("#4f410e", "#6e5c18", "#8f6f00", "#fbf0c9"), ("#261f06", "#3d3210", "#f5cf3d", "#3a3010")),
    "Psychic":   (("#4a1f50", "#66306e", "#9a35a8", "#f2dcf5"), ("#220d26", "#381640", "#e08af0", "#3a1a42")),
    "Fighting":  (("#5a3318", "#7a4724", "#a35b22", "#f6e2d0"), ("#26150a", "#3d2412", "#f0a868", "#3d2614")),
    "Darkness":  (("#1f2226", "#33383f", "#4a6585", "#dfe5ec"), ("#0b0c0e", "#1a1d22", "#9ab4d4", "#1e2833")),
    "Metal":     (("#3a4148", "#525b64", "#55707f", "#e1e8ed"), ("#15191c", "#252b30", "#a9c1d0", "#22313b")),
    "Dragon":    (("#3d3410", "#5a4c1a", "#7d6e1a", "#f0ecd0"), ("#1c180a", "#2e2812", "#d8c25a", "#33301a")),
    "Fairy":     (("#5a1f3d", "#7a2d55", "#b83f76", "#fbdbe8"), ("#260d1a", "#401528", "#f08ab8", "#401a2c")),
    "Colorless": (("#3d3d45", "#55555f", "#5f5f78", "#e6e6ec"), ("#16161a", "#26262c", "#b8b8cc", "#26262e")),
}

GUARD = """<script>
setTimeout(function () {
  if (window.__binderReady) return;
  var d = document.createElement("div");
  d.setAttribute("role", "alert");
  d.style.cssText = "margin:16px;padding:14px 16px;border-radius:10px;background:#fde8e6;color:#7a1d12;font:15px/1.5 system-ui,sans-serif";
  d.textContent = "The binder didn't finish loading. The Binder file in Apps Script is probably missing its last lines. Paste all of Binder.html into it again (the last line should be the End of Binder.html note), save, and deploy a new version.";
  document.body.insertBefore(d, document.body.firstChild);
}, 3000);
</script>
"""

STANDALONE_CSS = """
<style>
body { margin: 0; -webkit-text-size-adjust: 100%; }
[hidden] { display: none !important; }
img { max-width: 100%; }
.save-note.warn { color: #c0392b; }
:root[data-theme="dark"] .save-note.warn { color: #ff8a7a; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .save-note.warn { color: #ff8a7a; } }
</style>
"""


def must_replace(s, old, new):
    assert s.count(old) == 1, ("expected exactly one", old[:70], s.count(old))
    return s.replace(old, new)


def page_source(d):
    meta = json.load(open(f"{d}/meta.json", encoding="utf-8"))
    cards = open(f"{d}/data.json", encoding="utf-8").read()
    light, dark = THEMES.get(meta["type"], THEMES["Colorless"])
    title = meta.get("title") or f"{meta['pokemon']} Binder"
    dex = f"No. {meta['dex']:04d} · {meta['genus']}" if meta.get("dex") else "Pokémon TCG collection"
    s = open(f"{TPL}/binder.html", encoding="utf-8").read()
    for k, v in {"TITLE": title, "POKEMON": meta["pokemon"], "SLUG": meta["slug"], "DEX_LINE": dex,
                 "L_COVER": light[0], "L_COVER_HI": light[1], "L_ACCENT": light[2], "L_ACCENT_SOFT": light[3],
                 "D_COVER": dark[0], "D_COVER_HI": dark[1], "D_ACCENT": dark[2], "D_ACCENT_SOFT": dark[3],
                 "CARDS_JSON": cards}.items():
        s = s.replace("{{" + k + "}}", v)
    assert "{{" not in s.replace("{{CARDS", ""), "unfilled placeholder"
    return s, meta, title, light


def sync_code(slug, sync_url):
    """Replace the page's storage with this-device storage plus a queued sync to the Google Sheet."""
    return """/* Sync through a Google Sheet web app. This device keeps its own copy, plus a queue of changes not yet sent. */
const BAKED_SYNC_URL = """ + json.dumps(sync_url or "") + """;
const K_QUEUE = "%(slug)s-binder-queue", K_JOINED = "%(slug)s-binder-joined";
const store = {
  get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
};
const viaSheet = !!(window.google && google.script && google.script.run);
let syncUrl = viaSheet ? "sheet" : BAKED_SYNC_URL;
let queue = [];
try { queue = JSON.parse(store.get(K_QUEUE) || "[]"); } catch (e) {}
function saveQueue() { store.set(K_QUEUE, JSON.stringify(queue)); }
let syncing = false, again = false, syncTimer = null, lastOk = 0, lastErr = false;

function slotMeta(key) {
  const s = SLOTS.find(x => x.key === key);
  return s ? { card: s.card.name, set: s.card.set, num: `${s.card.num}/${s.card.total}`, finish: (s.ed ? s.ed + " " : "") + s.label } : {};
}
async function callSheet(ops) {
  if (viaSheet) {
    const r = await new Promise((resolve, reject) =>
      google.script.run.withSuccessHandler(resolve).withFailureHandler(reject).api(ops || []));
    if (!r || !r.ok) throw new Error("Sync failed");
    return r.owned || {};
  }
  const res = ops
    ? await fetch(syncUrl, { method: "POST", body: JSON.stringify({ ops }), redirect: "follow" })
    : await fetch(syncUrl + (syncUrl.includes("?") ? "&" : "?") + "t=" + Date.now(), { redirect: "follow" });
  const j = await res.json();
  if (!j.ok) throw new Error(j.error || "Sync failed");
  return j.owned || {};
}
function setNote() {
  const n = $("#save-note");
  n.classList.toggle("warn", !!syncUrl && lastErr);
  if (!syncUrl) n.textContent = "Saved on this device only.";
  else if (lastErr) n.textContent = `Can't reach the sync sheet. Changes are saved on this device${queue.length ? ` (${queue.length} waiting)` : ""} and will sync later.`;
  else if (lastOk) n.textContent = "Synced " + new Date(lastOk).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  else n.textContent = "Syncing…";
}
function scheduleSync(ms) { clearTimeout(syncTimer); syncTimer = setTimeout(sync, ms); }
async function sync() {
  if (!syncUrl) { setNote(); return; }
  if (syncing) { again = true; return; }
  syncing = true;
  try {
    let ops = queue.slice();
    const sent = ops.length;
    const joining = store.get(K_JOINED) !== syncUrl;
    if (joining) ops = [...owned.keys()].map(key => ({ key, have: true, at: owned.get(key).at })).concat(ops);
    const server = await callSheet(ops.length ? ops.map(op => ({ ...op, ...slotMeta(op.key) })) : null);
    queue = queue.slice(sent); saveQueue();
    if (joining) store.set(K_JOINED, syncUrl);
    const next = new Map(Object.entries(server));
    queue.forEach(op => op.have ? next.set(op.key, { have: true, at: op.at }) : next.delete(op.key));
    owned = next; saveLocal();
    lastOk = Date.now(); lastErr = false;
    render();
  } catch (e) {
    lastErr = true;
  } finally {
    syncing = false;
    setNote();
    if (again) { again = false; scheduleSync(300); }
  }
}
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") sync(); });
addEventListener("online", () => sync());
setInterval(() => { if (document.visibilityState === "visible") sync(); }, 30000);

loadLocal();
render();
setNote();
sync();
window.__binderReady = true;
""" % {"slug": slug}


SET_OWNED_SYNC = """function setOwned(key, have) {
  if (have) owned.set(key, { have: true, at: new Date().toISOString() }); else owned.delete(key);
  saveLocal();
  queue = queue.filter(op => op.key !== key);
  queue.push({ key, have, at: owned.get(key)?.at || new Date().toISOString() });
  saveQueue();
  render();
  scheduleSync(400);
}
"""


def standalone(src, meta, title, light, images, sync_url, guard):
    """Turn the artifact page into a complete HTML document that runs on its own or inside Apps Script."""
    head_end = src.index("</style>") + len("</style>")
    head, body = src[:head_end], src[head_end:]
    head = must_replace(head, ":root {\n  --desk", ":root {\n  padding-top: env(safe-area-inset-top, 0px);\n  padding-bottom: env(safe-area-inset-bottom, 0px);\n  --desk")
    head += STANDALONE_CSS
    body = must_replace(body, "const FIN = {", images[0] + "\n\nconst FIN = {")
    body = must_replace(body, 'src="cards/${esc(c.id)}.webp"', images[1])
    body = must_replace(body, 'width="440" height="614"', 'width="245" height="342"')
    a, b = body.index("async function setOwned("), body.index("function setReadOnly(")
    body = body[:a] + SET_OWNED_SYNC + body[b:]
    a = body.index("/* Boot:")
    b = body.index("</script>", a)
    body = body[:a] + sync_code(meta["slug"], sync_url) + body[b:]
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
           f'<meta name="theme-color" content="{light[0]}">\n' + head + "\n</head>\n<body>\n" + (GUARD if guard else "") + body.strip() + "\n</body>\n</html>\n")
    if guard:
        doc += "<!-- End of Binder.html. If you can see this line in Apps Script, the whole file was pasted. -->\n"
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("target", choices=["artifact", "sheet", "file"])
    ap.add_argument("--sync-url", default="")
    a = ap.parse_args()
    d = a.dir
    src, meta, title, light = page_source(d)
    sys.stdout.reconfigure(encoding="utf-8")

    if a.target == "artifact":
        out = f"{d}/artifact"
        os.makedirs(f"{out}/cards", exist_ok=True)
        open(f"{out}/{meta['slug']}-binder.html", "w", encoding="utf-8").write(src)
        files = {}
        for f in sorted(os.listdir(f"{d}/cards")):
            shutil.copy(f"{d}/cards/{f}", f"{out}/cards/{f}")
            files[f"cards/{f}"] = f"cards/{f}"
        json.dump(files, open(f"{out}/files.json", "w"), indent=0)
        print(f"Page: {out}/{meta['slug']}-binder.html\nRoot: {out}\nFiles map: {out}/files.json ({len(files)} images)")

    elif a.target == "sheet":
        out = f"{d}/sheet"
        os.makedirs(out, exist_ok=True)
        urls = json.load(open(f"{d}/imgurls.json"))
        images = ("const IMG = " + json.dumps(urls, separators=(",", ":")) + ";",
                  'src="${esc(IMG[c.id][opts.static ? 1 : 0])}"')
        doc = standalone(src, meta, title, light, images, a.sync_url, guard=True)
        open(f"{out}/Binder.html", "w", encoding="utf-8").write(doc)
        code = open(f"{TPL}/Code.gs.txt", encoding="utf-8").read().replace("{{TITLE}}", title)
        open(f"{out}/Code.gs.txt", "w", encoding="utf-8").write(code)
        print(f"Binder page: {out}/Binder.html ({len(doc.encode()) // 1024} KB, {doc.count(chr(10))} lines)\nScript: {out}/Code.gs.txt")

    else:
        imgs = {f[:-5]: base64.b64encode(open(f"{d}/small/{f}", "rb").read()).decode() for f in sorted(os.listdir(f"{d}/small"))}
        images = ("const IMG = " + json.dumps(imgs, separators=(",", ":")) + """;
const imgCache = {};
function imgUrl(id) {
  if (!imgCache[id]) {
    const bin = atob(IMG[id]);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    imgCache[id] = URL.createObjectURL(new Blob([bytes], { type: "image/webp" }));
  }
  return imgCache[id];
}""", 'src="${imgUrl(c.id)}"')
        doc = standalone(src, meta, title, light, images, a.sync_url, guard=False)
        path = f"{d}/{title}.html"
        open(path, "w", encoding="utf-8").write(doc)
        print(f"File: {path} ({len(doc.encode()) / 1e6:.1f} MB){' with sync' if a.sync_url else ', saves on the device only'}")


if __name__ == "__main__":
    main()
