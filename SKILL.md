---
name: pokemon-binder
description: Build an interactive, flip-through Pokémon card binder for collecting every English printing of one Pokémon, with a pocket per finish (holo, reverse holo, non-holo, 1st Edition, Unlimited), card images, and a collected checkmark that syncs between phones through a Google Sheet. Use when the user wants a binder, checklist or collection tracker for a Pokémon ("make a Zapdos binder", "binder for every Charizard card", "track my Mew collection"), or wants to update or fix one of these binders.
---

# Pokémon binder

Builds the same binder as the original Articuno Binder: a leather binder on a desk, 9-pocket pages (two-page spread with a page-turn animation on wide screens and unfolded foldables, one page on phones), finish badges on every pocket, foil shimmer on collected holos, filters (Missing / Collected, by finish), Jump to set, and a details view per card. The cover and accent colors follow the Pokémon's main TCG type.

Scripts live in this skill folder: `scripts/fetch_cards.py`, `scripts/build.py`. Templates: `templates/binder.html`, `templates/Code.gs.txt`.

## 1. Settle the Pokémon and the delivery

Ask only what's unclear. Delivery options, recommend the first:

| Target | Works on | Sync | Use when |
|---|---|---|---|
| `sheet` (Google Sheet web app) | Every phone and browser, iPhone included | Yes, everyone with the link shares one collection | Default. Sharing with family or friends |
| `artifact` (Claude artifact) | Anyone signed in to claude.ai the user shares it with | Yes | User wants it inside Claude |
| `file` (single HTML file, images inside) | Android and computers only. **iPhones open HTML files in a preview that doesn't run code** | Only with `--sync-url` | Offline copy |

Each binder gets its own Google Sheet and its own web app link.

## 2. Fetch the cards

Work in the session scratchpad (`<scratchpad>/binders/<slug>`); the scripts write raw images and caches there.

```
python <skill>/scripts/fetch_cards.py "Zapdos" --out <work dir>
```

- Matches every card whose name contains the Pokémon (Galarian, Dark, Rocket's, ex, GX, V, tag teams).
- Names that contain another Pokémon's name (Mew → Mewtwo, Pikachu → Pikachu libre is fine, Abra → Kadabra): use `--exact`, or `--exclude "Mewtwo,Mewtwo ex"`. Check the "Distinct card names" line every time.
- Re-runs reuse `cards.json` and downloaded images; pass `--query` to force a new search.
- The Pokémon TCG API sometimes answers 500 or 504. The script retries four times with a growing wait; if it still fails, wait a minute and run it again.

Review the printed table. Finishes come from TCGplayer price listings and are mostly right, but fix these, then write `<work dir>/overrides.json` and re-run:

- Lines marked `GUESSED` (no price data yet, common for brand-new sets).
- ex / EX / GX / V / VMAX / VSTAR cards list a stray `normal`: they're holo only.
- e-Card "H" numbers (H1–H32) are holo only. Legendary Collection cards have a reverse holo.
- Promos vary: WotC Black Star promos are mostly non-holo, modern promos holo.
- Southern Islands cards (`si1-*`) are all holo, but the price data lists them as `normal`.
- McDonald's collections (`mcd*`) usually came in both holo and non-holo; the price data lists only one. Give them `["normal", "holofoil"]`.
- Cards with a blank rarity (Southern Islands, McDonald's, Pokémon Rumble) deserve a second look.

```json
{ "variants": { "ex7-106": ["holofoil"], "base6-19": ["holofoil", "reverseHolofoil"] },
  "exclude_ids": ["some-id"] }
```

Finish keys: `normal`, `holofoil`, `reverseHolofoil`, `1stEdition`, `unlimited`, `1stEditionHolofoil`, `unlimitedHolofoil`.

Tell the user the count (printings and pockets) and anything you excluded or guessed, in a few lines. Don't paste the whole table. Coverage is English cards in the Pokémon TCG database (McDonald's collections included): no Japanese cards and no stamped or prerelease variants.

## 3. Build

```
python <skill>/scripts/build.py <work dir> sheet       # Binder.html + Code.gs.txt in <work dir>/sheet
python <skill>/scripts/build.py <work dir> artifact    # page + cards/ + files.json in <work dir>/artifact
python <skill>/scripts/build.py <work dir> file [--sync-url URL]
```

Optional: put `"title": "Our Zapdos Binder"` in `<work dir>/meta.json` before building to rename it.

Check it renders. On Windows, headless Edge does this without opening a window:

```powershell
$e = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$dom = & $e --headless=new --disable-gpu "--user-data-dir=<work dir>\prof" --virtual-time-budget=6000 --dump-dom "file:///<path to html>" 2>$null | Out-String
([regex]::Matches($dom, 'class="pocket k-')).Count   # 18 or 19 means the first spread drew
```

For a look, use `--screenshot=<png> --window-size=800,1100` and Read the PNG. Narrow phone widths can't be shot directly (Edge won't shrink its window that far): load the page in a 340px or 412px `<iframe>` inside a test page, with `--allow-file-access-from-files`.

## 4. Deliver

Copy the deliverables into a `<Pokémon> Binder` folder in the user's working directory and link them.

### sheet: set it up in Chrome (preferred)

When Claude in Chrome is connected, do the Google side yourself so the user copies and pastes nothing. Load the chrome-browser skill first, then load these tools in one ToolSearch: `tabs_context_mcp, tabs_create_mcp, tabs_close_mcp, navigate, computer, find, javascript_tool, browser_batch, file_upload`. Take a 0.6-scale screenshot before clicking by coordinates; use `find` refs for dropdown options (coordinate clicks on list options often miss).

Apps Script's menus and dialogs sometimes open a beat late or not on the first click (the Deploy menu, the Rename dialog). Screenshot after each click; if nothing opened, click once more. Don't type until the dialog is visible, or the text lands in the editor. The project title in the header can lag after a rename; the tab title shows the new name right away. Google strips comments and escapes characters like `=` and `;` when it serves the page, so check a served page for plain identifiers (as with `__binderReady` below), never for comments or code snippets.

1. **Sheet.** Navigate a new tab to `https://sheets.new`. Click the "Untitled spreadsheet" title, Ctrl+A, type "<Pokémon> Binder", Enter. Confirm in a screenshot that the account avatar is the user's personal Gmail.
2. **Apps Script.** The Extensions menu is often hidden in a narrow window. Press `alt+/` (menu search), type "Apps Script", click the result. The editor opens in a new tab; get its id from `tabs_context_mcp`.
3. **Load the files without pasting.** The editor exposes `window.monaco`. Add a file input to the page, then upload both local files into it:
   ```js
   document.getElementById('cf-binder-upload')?.remove();
   const inp = Object.assign(document.createElement('input'), { type: 'file', multiple: true, id: 'cf-binder-upload' });
   inp.setAttribute('aria-label', 'Binder files upload');
   inp.style.cssText = 'position:fixed;bottom:8px;left:8px;z-index:99999;background:#fff';
   document.body.appendChild(inp);
   ```
   `find` "Binder files upload file input" → `file_upload` with the paths of `Code.gs.txt` and `Binder.html` (from the deliverables folder). Then read them: `window.__binderFiles = {}; for (const f of inp.files) window.__binderFiles[f.name] = await f.text();`
4. **Code.gs.** With Code.gs open (its model uri ends in `.js`):
   ```js
   const ed = monaco.editor.getEditors()[0], m = ed.getModel(), t = window.__binderFiles['Code.gs.txt'];
   ed.executeEdits('binder-setup', [{ range: m.getFullModelRange(), text: t }]); ed.focus();
   m.getValue() === t.replace(/\r\n/g, '\n')   // must be true (the editor stores LF line endings)
   ```
   Press Ctrl+S; the header shows "Saved to Drive".
5. **Binder file.** Click the + next to Files → HTML, type `Binder`, Enter. The new file opens (uri ends in `.html`). Run the same edit with `Binder.html`, check it matches, Ctrl+S.
6. **Project name.** Click the "Untitled project" title; a Rename dialog opens with the text selected. Type "<Pokémon> Binder", click Rename.
7. **Deploy.** Deploy → New deployment → gear next to "Select type" → Web app. Who has access: open the list and click the `find` ref for the option exactly "Anyone" (not "Anyone with Google account"). Execute as stays "Me". Zoom to confirm, then click Deploy.
8. **Authorization is the user's click.** Google shows "Authorize access". Stop and ask the user to do it: Authorize access → pick their Gmail → Advanced → Go to <project> (unsafe) → Allow. Wait for them to say done.
9. **Get the link.** `[...document.querySelectorAll('a')].map(a => a.href).filter(h => h.includes('/macros/s/'))`, then click Done.
10. **Verify** with the curl checks below, then navigate a tab to the link and screenshot: the page should say "Synced <time>" (that line proves the sheet sync works inside Google). Close the tabs you opened and give the user the link.

**Updating an existing binder in Chrome** (new cards, fixes, or switching it to another Pokémon): open the project (script.google.com → the project, or the sheet → `alt+/` → Apps Script), repeat steps 3–5 on the existing files (click a file in the Files list to open it before editing; check the model uri), rename the project and sheet if the Pokémon changed, then Deploy → Manage deployments → pencil → Version list → `find` "New version" → Deploy. No new authorization is needed. Switching Pokémon leaves no stale data behind: pocket keys include card ids, so old rows simply never match.

### sheet: manual setup (when Chrome isn't connected)

Give the user these steps (personal Google account; a school account may block "Anyone" access):

1. Go to sheets.new and name the sheet "<Pokémon> Binder".
2. Extensions → Apps Script. In Code.gs, delete everything and paste all of `Code.gs.txt`.
3. Click + next to Files → HTML, name it exactly `Binder`, delete its contents and paste all of `Binder.html`. Open the file in Notepad, Ctrl+A, Ctrl+C. Scroll to the bottom: the last line must be the "End of Binder.html" note, or the paste was cut off.
4. Save. Deploy → New deployment → gear → Web app. Execute as: Me. Who has access: Anyone. Deploy.
5. Authorize. Google warns the app isn't verified; click Advanced → Go to (project) → Allow.
6. Copy the Web app URL (ends in `/exec`) and send it back.

When they send the link, check it:

```bash
curl -sL "<url>?t=1"            # expect {"ok":true,"owned":{...}}
curl -sL "<url>" | grep -o "__binderReady" | wc -l  # 2 = the whole page was pasted, 1 = cut off, 0 = an old build without the check
```

Then tell them: open the link in any browser; on iPhone, Share → Add to Home Screen. Google's gray "created by another user" banner is normal. Anyone with the link can change the collection.

### sheet (updates)

Paste the new `Binder.html` (and `Code.gs.txt` only if it changed), Save, then Deploy → **Manage deployments** → pencil → Version: **New version** → Deploy. Never "New deployment" for an update: that makes a new link and old copies stop syncing.

### artifact

Publish `<work dir>/artifact/<slug>-binder.html` with `root` = `<work dir>/artifact`, `files` = the map in `files.json`, `capabilities: {"db": {}, "user": {}}`, `icon: "cards"`. The collection lives in the artifact's `owned` collection (one doc per pocket key `<card id>~<finish>`); check it once with ArtifactData `list`. It's private until the user shares it, and a viewer needs Contributor or Editor access to check cards.

### file

Send it with SendUserFile (`display: attach`). Say plainly it won't run on iPhones, and that without `--sync-url` the checkmarks stay on that device.

## Writing

Plain, specific copy in the page and in replies. No slang, no emoji.
