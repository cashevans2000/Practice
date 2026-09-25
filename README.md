Practicing coding

## Code Clicker (Python incremental game)

A terminal incremental/idle game written with the Python standard library.

```
python3 incremental_game.py
```

- Press **Enter** (or `c [n]`) to write code by hand.
- `b <#> [n|max]` hires developers who write code for you every second.
- `u <id>` buys upgrades that multiply clicks or production.
- Earn 1M lines in a run, then `ship` to reset for **Stars** (+10% production each).
- Progress autosaves to `~/.code_clicker_save.json`; you earn 50% of your income while away (up to 8 hours).

Run the tests with `python3 -m unittest test_incremental_game`.

### Play in the browser

`web/code_clicker.html` is a browser version with the same balance: click (or focus and type in) the editor to write code, hire developers ×1/×10/Max, buy upgrades, and ship for Stars. It saves to your browser's local storage. Open the file directly in any browser.
