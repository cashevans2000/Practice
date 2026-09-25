#!/usr/bin/env python3
"""Code Clicker - a terminal incremental game.

Write lines of code by hand, hire developers who write code for you,
buy upgrades, and eventually "ship" your product to earn Stars that
permanently boost everything.

Income keeps accumulating in real time between commands, and progress
earned while the game is closed is credited (at a reduced rate) when you
come back. Standard library only.
"""

import json
import math
import os
import sys
import time

SAVE_FILE = os.path.join(os.path.expanduser("~"), ".code_clicker_save.json")
OFFLINE_RATE = 0.5          # fraction of income earned while the game is closed
OFFLINE_CAP_SECONDS = 8 * 3600
COST_GROWTH = 1.15
PRESTIGE_THRESHOLD = 1_000_000
STAR_BONUS = 0.10           # +10% production per Star

# name, base cost, lines per second
GENERATORS = [
    ("Intern",          15,          0.1),
    ("Junior Dev",      100,         1),
    ("Senior Dev",      1_100,       8),
    ("AI Assistant",    12_000,      47),
    ("Dev Team",        130_000,     260),
    ("Startup",         1_400_000,   1_400),
    ("Tech Giant",      20_000_000,  7_800),
]

# id, name, description, cost, kind, target, multiplier
# kind "click": multiplies lines per click
# kind "gen":   multiplies one generator's output (target = generator index)
# kind "all":   multiplies all generator output
UPGRADES = [
    ("kb",      "Mechanical Keyboard", "Clicks x2",            100,        "click", None, 2),
    ("coffee",  "Coffee Machine",      "Interns x2",           500,        "gen",   0,    2),
    ("ide",     "Better IDE",          "Clicks x3",            5_000,      "click", None, 3),
    ("mentor",  "Mentorship Program",  "Junior Devs x2",       10_000,     "gen",   1,    2),
    ("standup", "Daily Standups",      "All production x1.5",  50_000,     "all",   None, 1.5),
    ("review",  "Code Reviews",        "Senior Devs x2",       100_000,    "gen",   2,    2),
    ("gpu",     "GPU Cluster",         "AI Assistants x3",     1_000_000,  "gen",   3,    3),
    ("agile",   "Agile Coach",         "Dev Teams x2",         10_000_000, "gen",   4,    2),
    ("vc",      "Venture Capital",     "All production x2",    50_000_000, "all",   None, 2),
    ("macro",   "Keyboard Macros",     "Clicks +1% of LPS",    250_000,    "click", None, 1),
]

SUFFIXES = ["", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc"]


def fmt(n):
    """Format a number compactly, e.g. 1234567 -> '1.23M'."""
    if n < 1000:
        return f"{n:.1f}".rstrip("0").rstrip(".") if n % 1 else f"{int(n)}"
    exp = min(int(math.log10(n) // 3), len(SUFFIXES) - 1)
    return f"{n / 1000 ** exp:.2f}{SUFFIXES[exp]}"


def fmt_time(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


class Game:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lines = 0.0
        self.total_lines = 0.0      # earned this run, used for prestige
        self.lifetime_lines = 0.0
        self.owned = [0] * len(GENERATORS)
        self.upgrades = set()
        self.stars = 0
        self.clicks = 0
        self.last_tick = clock()

    # ---- derived values -------------------------------------------------

    def star_multiplier(self):
        return 1 + STAR_BONUS * self.stars

    def global_multiplier(self):
        mult = self.star_multiplier()
        for uid, _, _, _, kind, _, m in UPGRADES:
            if kind == "all" and uid in self.upgrades:
                mult *= m
        return mult

    def generator_rate(self, i):
        """Lines per second produced by ONE unit of generator i."""
        rate = GENERATORS[i][2]
        for uid, _, _, _, kind, target, m in UPGRADES:
            if kind == "gen" and target == i and uid in self.upgrades:
                rate *= m
        return rate * self.global_multiplier()

    def lps(self):
        return sum(self.generator_rate(i) * n for i, n in enumerate(self.owned))

    def click_power(self):
        power = 1.0
        for uid, _, _, _, kind, _, m in UPGRADES:
            if kind == "click" and uid in self.upgrades and uid != "macro":
                power *= m
        power *= self.star_multiplier()
        if "macro" in self.upgrades:
            power += 0.01 * self.lps()
        return power

    def generator_cost(self, i, owned=None):
        owned = self.owned[i] if owned is None else owned
        return math.ceil(GENERATORS[i][1] * COST_GROWTH ** owned)

    def bulk_cost(self, i, amount):
        return sum(self.generator_cost(i, self.owned[i] + k) for k in range(amount))

    def stars_on_prestige(self):
        """Stars gained by shipping now (sqrt scaling on this run's earnings)."""
        if self.total_lines < PRESTIGE_THRESHOLD:
            return 0
        return int(math.sqrt(self.total_lines / PRESTIGE_THRESHOLD))

    # ---- actions --------------------------------------------------------

    def earn(self, amount):
        self.lines += amount
        self.total_lines += amount
        self.lifetime_lines += amount

    def tick(self):
        """Credit income for real time elapsed since the last tick."""
        now = self.clock()
        elapsed = max(0.0, now - self.last_tick)
        self.last_tick = now
        self.earn(self.lps() * elapsed)
        return elapsed

    def click(self, times=1):
        gained = self.click_power() * times
        self.clicks += times
        self.earn(gained)
        return gained

    def buy_generator(self, i, amount=1):
        if not 0 <= i < len(GENERATORS):
            return False, "No such generator."
        if amount == "max":
            amount = 0
            total = 0
            while True:
                next_cost = self.generator_cost(i, self.owned[i] + amount)
                if total + next_cost > self.lines:
                    break
                total += next_cost
                amount += 1
            if amount == 0:
                return False, f"Can't afford a {GENERATORS[i][0]}."
        cost = self.bulk_cost(i, amount)
        if cost > self.lines:
            return False, f"Need {fmt(cost)} lines (you have {fmt(self.lines)})."
        self.lines -= cost
        self.owned[i] += amount
        return True, f"Hired {amount} x {GENERATORS[i][0]} for {fmt(cost)} lines."

    def buy_upgrade(self, uid):
        for u in UPGRADES:
            if u[0] == uid:
                if uid in self.upgrades:
                    return False, "Already purchased."
                if u[3] > self.lines:
                    return False, f"Need {fmt(u[3])} lines (you have {fmt(self.lines)})."
                self.lines -= u[3]
                self.upgrades.add(uid)
                return True, f"Bought {u[1]}: {u[2]}."
        return False, "No such upgrade."

    def prestige(self):
        gained = self.stars_on_prestige()
        if gained == 0:
            return False, f"Earn {fmt(PRESTIGE_THRESHOLD)} lines this run to ship."
        stars, lifetime, clicks = self.stars + gained, self.lifetime_lines, self.clicks
        self.__init__(self.clock)
        self.stars, self.lifetime_lines, self.clicks = stars, lifetime, clicks
        return True, f"Shipped! +{gained} Stars (now {stars}, +{int(STAR_BONUS * 100 * stars)}% production)."

    # ---- persistence ----------------------------------------------------

    def to_dict(self):
        return {
            "lines": self.lines,
            "total_lines": self.total_lines,
            "lifetime_lines": self.lifetime_lines,
            "owned": self.owned,
            "upgrades": sorted(self.upgrades),
            "stars": self.stars,
            "clicks": self.clicks,
            "saved_at": self.clock(),
        }

    @classmethod
    def from_dict(cls, data, clock=time.time):
        g = cls(clock)
        g.lines = data.get("lines", 0.0)
        g.total_lines = data.get("total_lines", 0.0)
        g.lifetime_lines = data.get("lifetime_lines", 0.0)
        owned = data.get("owned", [])
        g.owned = (owned + [0] * len(GENERATORS))[:len(GENERATORS)]
        valid = {u[0] for u in UPGRADES}
        g.upgrades = set(data.get("upgrades", [])) & valid
        g.stars = data.get("stars", 0)
        g.clicks = data.get("clicks", 0)
        g.last_tick = g.clock()
        return g

    def apply_offline(self, saved_at):
        away = min(max(0.0, self.clock() - saved_at), OFFLINE_CAP_SECONDS)
        gained = self.lps() * away * OFFLINE_RATE
        self.earn(gained)
        return away, gained

    def save(self, path=SAVE_FILE):
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f)
        os.replace(tmp, path)


def load_game(path=SAVE_FILE):
    """Return (game, message). Starts fresh if no valid save exists."""
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return Game(), "New game started. Type 'help' for commands."
    except (OSError, json.JSONDecodeError):
        return Game(), "Save file was unreadable; starting a new game."
    game = Game.from_dict(data)
    away, gained = game.apply_offline(data.get("saved_at", game.clock()))
    msg = "Welcome back!"
    if gained > 0:
        msg += f" While you were away ({fmt_time(away)}) your team wrote {fmt(gained)} lines."
    return game, msg


# ---- terminal UI ----------------------------------------------------------

HELP = """
Commands:
  <Enter> or c [n]   write code by hand (n times)
  b <#> [n|max]      hire generator # (optionally n of them, or as many as you can)
  u <id>             buy an upgrade (see list)
  ship               prestige: reset for Stars (+10% production each)
  stats              show lifetime stats
  save               save now (the game also autosaves)
  reset              wipe your save and start over
  help               show this help
  q                  save and quit
"""


def render(game):
    lines = []
    lines.append("=" * 60)
    lines.append(f"  LINES OF CODE: {fmt(game.lines):>10}    "
                 f"per second: {fmt(game.lps())}    per click: {fmt(game.click_power())}")
    if game.stars:
        lines.append(f"  Stars: {game.stars} (+{int(STAR_BONUS * 100 * game.stars)}% production)")
    lines.append("-" * 60)
    lines.append("  #  Generator        Owned        Cost     LPS each")
    for i, (name, _, _) in enumerate(GENERATORS):
        # Reveal generators once the player can nearly afford them.
        if i > 0 and game.owned[i] == 0 and game.owned[i - 1] == 0 \
                and game.lifetime_lines < GENERATORS[i][1] * 0.5:
            lines.append(f"  {i + 1}  ???")
            break
        cost = game.generator_cost(i)
        mark = "*" if cost <= game.lines else " "
        lines.append(f" {mark}{i + 1}  {name:<15} {game.owned[i]:>5} {fmt(cost):>11}   {fmt(game.generator_rate(i)):>8}")
    available = [u for u in UPGRADES
                 if u[0] not in game.upgrades and game.lifetime_lines >= u[3] * 0.25]
    if available:
        lines.append("-" * 60)
        lines.append("  Upgrades")
        for uid, name, desc, cost, *_ in available:
            mark = "*" if cost <= game.lines else " "
            lines.append(f" {mark}{uid:<8} {name:<20} {desc:<22} {fmt(cost):>8}")
    stars = game.stars_on_prestige()
    if stars:
        lines.append("-" * 60)
        lines.append(f"  Ready to ship! Type 'ship' to gain {stars} Star(s).")
    lines.append("=" * 60)
    return "\n".join(lines)


def handle(game, cmd):
    """Process one command. Returns (message, keep_running)."""
    parts = cmd.strip().lower().split()
    if not parts or parts[0] in ("c", "click"):
        times = 1
        if len(parts) > 1:
            if not parts[1].isdigit():
                return "Usage: c [n]", True
            times = max(1, min(int(parts[1]), 100))
        return f"+{fmt(game.click(times))} lines", True
    verb = parts[0]
    if verb in ("b", "buy"):
        if len(parts) < 2 or not parts[1].isdigit():
            return "Usage: b <#> [n|max]", True
        amount = 1
        if len(parts) > 2:
            if parts[2] == "max":
                amount = "max"
            elif parts[2].isdigit() and int(parts[2]) > 0:
                amount = int(parts[2])
            else:
                return "Usage: b <#> [n|max]", True
        return game.buy_generator(int(parts[1]) - 1, amount)[1], True
    if verb in ("u", "upgrade"):
        if len(parts) < 2:
            return "Usage: u <id>", True
        return game.buy_upgrade(parts[1])[1], True
    if verb in ("ship", "prestige"):
        return game.prestige()[1], True
    if verb == "stats":
        return (f"Lifetime lines: {fmt(game.lifetime_lines)} | This run: {fmt(game.total_lines)} | "
                f"Hand-written clicks: {game.clicks} | Stars: {game.stars}"), True
    if verb == "save":
        game.save()
        return "Game saved.", True
    if verb == "reset":
        try:
            confirm = input("Really wipe ALL progress? Type 'yes': ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            confirm = ""
        if confirm == "yes":
            game.__init__(game.clock)
            return "Progress wiped.", True
        return "Reset cancelled.", True
    if verb in ("h", "help", "?"):
        return HELP, True
    if verb in ("q", "quit", "exit"):
        return "Saved. See you soon!", False
    return f"Unknown command '{verb}'. Type 'help'.", True


def main():
    game, message = load_game()
    last_save = time.time()
    running = True
    while running:
        game.tick()
        print("\n" + render(game))
        if message:
            print(f"  > {message}")
        try:
            cmd = input("> ")
        except (EOFError, KeyboardInterrupt):
            print()
            cmd = "q"
        game.tick()
        message, running = handle(game, cmd)
        if time.time() - last_save > 30:
            game.save()
            last_save = time.time()
    game.save()
    print(message)


if __name__ == "__main__":
    sys.exit(main())
