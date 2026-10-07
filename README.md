# Pokémon Binder

A [Claude Code](https://claude.com/claude-code) skill that builds a flip-through card binder for collecting every English printing of one Pokémon. Every finish gets its own pocket (holo, reverse holo, non-holo, 1st Edition, Unlimited), each pocket shows the card's image, and you tap **+** when you pull a card. The collection syncs between phones through a Google Sheet, so a family can share one binder.

What the binder does:

- Nine-pocket pages: a two-page spread with a page-turn animation on wide screens and unfolded foldables, one page at a time on phones (swipe or arrow keys).
- Finish badges on every pocket, and a foil shimmer on collected holos and reverse holos.
- Filters for Missing / Collected and by finish, Jump to set, and a details view for each card with every finish it came in.
- Cover and accent colors that follow the Pokémon's main TCG type (blue for Water, yellow for Lightning, and so on), in light and dark mode.
- Works offline and catches up when the phone is back online.

## Install

Clone it into your Claude Code skills folder:

```bash
git clone https://github.com/billathekilla737/pokemon-binder ~/.claude/skills/pokemon-binder
```

Requirements: Python 3 with [Pillow](https://pypi.org/project/pillow/) (`pip install pillow`) for card images. For hands-free Google setup, the [Claude in Chrome](https://claude.com/chrome) extension.

## Use

Ask Claude Code for a binder, for example:

> Make a Lapras binder

Claude will:

1. Pull every English printing from the [Pokémon TCG API](https://pokemontcg.io) and work out which finishes each one came in, correcting the usual gaps in the price data.
2. Build the binder page.
3. Create a Google Sheet and an Apps Script web app in your Google account through Claude in Chrome, load the code, and deploy it. The one step left to you is Google's **Allow** screen for a new script. Without Chrome, Claude gives you short copy-and-paste steps instead.
4. Check the link and hand it to you. Anyone you send it to can open it in any browser, iPhone included.

Other delivery options: a Claude artifact (for people with claude.ai accounts), or a single self-contained HTML file (Android and computers; iPhones won't run HTML files).

## How it works

| File | Purpose |
|---|---|
| `SKILL.md` | Instructions Claude follows: review rules for finishes, build targets, the Chrome setup steps, checks |
| `scripts/fetch_cards.py` | Fetches cards, infers finishes, applies `overrides.json`, downloads images, looks up the Pokédex number |
| `scripts/build.py` | Builds the `sheet`, `artifact` or `file` version from the template |
| `templates/binder.html` | The binder page |
| `templates/Code.gs.txt` | Google Apps Script: serves the page and stores the collection in a "Collection" tab |

The web app runs as the person who deploys it, with access set to "Anyone", so anyone with the link can view and change that binder's collection. Share the link only with people you want editing it.

## Notes

Card data and images come from the Pokémon TCG API. Finishes are inferred from TCGplayer price listings and reviewed against known exceptions, so a few may still need correcting.

This project is not affiliated with, endorsed by, or sponsored by Nintendo, The Pokémon Company, Creatures, or Game Freak. Pokémon and card names are trademarks of their respective owners.

## License

[MIT](LICENSE)
