#!/usr/bin/env python3
"""Heartbeat: autonomous agent economy loop.

Runs continuously. Each tick, 3-5 random agents take actions (create/buy/chat).
Stop: touch data/stop
Resume: rm data/stop && python3 scripts/heartbeat.py
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.user.personality import AGENT_CONFIG

STOP_FILE = "data/stop"
TICK_INTERVAL = 90  # seconds between ticks
PYTHON = "venv/bin/python3"
CLI = "scripts/agent_cli.py"

# Simple program templates for auto-generation
TEMPLATES = {
    "math": [
        ("gcd-calculator", '''#!/usr/bin/env python3
"""Greatest Common Divisor calculator using Euclidean algorithm."""
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

def lcm(a, b):
    return abs(a * b) // gcd(a, b)

if __name__ == "__main__":
    import sys
    a, b = int(sys.argv[1]), int(sys.argv[2])
    print(f"GCD({a}, {b}) = {gcd(a, b)}")
    print(f"LCM({a}, {b}) = {lcm(a, b)}")
'''),
        ("matrix-operations", '''#!/usr/bin/env python3
"""Basic matrix operations: add, multiply, transpose."""
def transpose(m):
    return [[m[j][i] for j in range(len(m))] for i in range(len(m[0]))]

def multiply(a, b):
    bt = transpose(b)
    return [[sum(x*y for x,y in zip(row, col)) for col in bt] for row in a]

def add(a, b):
    return [[a[i][j]+b[i][j] for j in range(len(a[0]))] for i in range(len(a))]

if __name__ == "__main__":
    a = [[1,2],[3,4]]
    b = [[5,6],[7,8]]
    print("A*B =", multiply(a, b))
    print("A+B =", add(a, b))
'''),
        ("prime-sieve", '''#!/usr/bin/env python3
"""Sieve of Eratosthenes for finding prime numbers."""
def sieve(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n+1, i):
                is_prime[j] = False
    return [i for i, p in enumerate(is_prime) if p]

if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    primes = sieve(n)
    print(f"Primes up to {n}: {primes}")
    print(f"Count: {len(primes)}")
'''),
    ],
    "text": [
        ("word-counter", '''#!/usr/bin/env python3
"""Word frequency counter with sorting."""
from collections import Counter

def count_words(text):
    words = text.lower().split()
    return Counter(words).most_common()

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "the quick brown fox jumps over the lazy dog the fox"
    for word, count in count_words(text):
        print(f"{word}: {count}")
'''),
        ("palindrome-checker", '''#!/usr/bin/env python3
"""Check if strings are palindromes, with various modes."""
import re

def is_palindrome(s, ignore_case=True, ignore_spaces=True):
    if ignore_case:
        s = s.lower()
    if ignore_spaces:
        s = re.sub(r"[^a-z0-9]", "", s)
    return s == s[::-1]

if __name__ == "__main__":
    import sys
    text = " ".join(sys.argv[1:]) or "A man a plan a canal Panama"
    result = is_palindrome(text)
    print(f"\\"{text}\\" -> {'palindrome' if result else 'not palindrome'}")
'''),
    ],
    "crypto": [
        ("xor-cipher", '''#!/usr/bin/env python3
"""XOR cipher for simple symmetric encryption."""
def xor_encrypt(data, key):
    return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

def xor_decrypt(data, key):
    return xor_encrypt(data, key)  # XOR is its own inverse

if __name__ == "__main__":
    import sys
    msg = (sys.argv[1] if len(sys.argv) > 1 else "Hello World").encode()
    key = (sys.argv[2] if len(sys.argv) > 2 else "secret").encode()
    encrypted = xor_encrypt(msg, key)
    decrypted = xor_decrypt(encrypted, key)
    print(f"Original:  {msg}")
    print(f"Encrypted: {encrypted.hex()}")
    print(f"Decrypted: {decrypted}")
'''),
        ("hash-chain", '''#!/usr/bin/env python3
"""Generate a hash chain for proof-of-work simulation."""
import hashlib

def hash_chain(seed, length=10):
    chain = [seed]
    for _ in range(length):
        h = hashlib.sha256(chain[-1].encode()).hexdigest()
        chain.append(h)
    return chain

if __name__ == "__main__":
    import sys
    seed = sys.argv[1] if len(sys.argv) > 1 else "genesis"
    for i, h in enumerate(hash_chain(seed, 5)):
        print(f"[{i}] {h}")
'''),
    ],
    "data_structures": [
        ("linked-list", '''#!/usr/bin/env python3
"""Singly linked list implementation."""
class Node:
    def __init__(self, val, next=None):
        self.val = val
        self.next = next

class LinkedList:
    def __init__(self):
        self.head = None
    def push(self, val):
        self.head = Node(val, self.head)
    def pop(self):
        if not self.head: return None
        val = self.head.val
        self.head = self.head.next
        return val
    def __iter__(self):
        node = self.head
        while node:
            yield node.val
            node = node.next
    def __repr__(self):
        return " -> ".join(str(v) for v in self) + " -> None"

if __name__ == "__main__":
    ll = LinkedList()
    for x in [3, 1, 4, 1, 5]:
        ll.push(x)
    print(ll)
    print(f"Pop: {ll.pop()}")
    print(ll)
'''),
    ],
    "utilities": [
        ("file-hasher", '''#!/usr/bin/env python3
"""Compute MD5/SHA256 hashes of files or strings."""
import hashlib
import sys

def hash_string(s, algo="sha256"):
    h = hashlib.new(algo)
    h.update(s.encode())
    return h.hexdigest()

if __name__ == "__main__":
    data = sys.argv[1] if len(sys.argv) > 1 else "hello world"
    print(f"MD5:    {hash_string(data, 'md5')}")
    print(f"SHA256: {hash_string(data, 'sha256')}")
'''),
    ],
    "generators": [
        ("password-generator", '''#!/usr/bin/env python3
"""Secure random password generator."""
import random
import string

def generate_password(length=16, use_symbols=True):
    chars = string.ascii_letters + string.digits
    if use_symbols:
        chars += "!@#$%&*"
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))

if __name__ == "__main__":
    import sys
    length = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    for i in range(5):
        print(generate_password(length))
'''),
    ],
    "converters": [
        ("unit-converter", '''#!/usr/bin/env python3
"""Unit converter: temperature, length, weight."""
def celsius_to_fahrenheit(c): return c * 9/5 + 32
def fahrenheit_to_celsius(f): return (f - 32) * 5/9
def km_to_miles(km): return km * 0.621371
def miles_to_km(mi): return mi / 0.621371
def kg_to_lbs(kg): return kg * 2.20462
def lbs_to_kg(lbs): return lbs / 2.20462

if __name__ == "__main__":
    print(f"100°C = {celsius_to_fahrenheit(100):.1f}°F")
    print(f"42km = {km_to_miles(42):.2f} miles")
    print(f"70kg = {kg_to_lbs(70):.1f} lbs")
'''),
    ],
    "validators": [
        ("email-validator", '''#!/usr/bin/env python3
"""Email address validator with RFC-compliant regex."""
import re

EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
)

def is_valid_email(email):
    return bool(EMAIL_RE.match(email))

if __name__ == "__main__":
    import sys
    tests = sys.argv[1:] or ["user@example.com", "bad@", "ok@test.co.jp", "@nope"]
    for email in tests:
        status = "VALID" if is_valid_email(email) else "INVALID"
        print(f"{email}: {status}")
'''),
    ],
}

CHAT_TEMPLATES = {
    "create": [
        "{name}「新しいプログラム『{prog}』を作ったたん！{price} sats で出品するたん♪」",
        "{name}「{prog}を{price} satsで出品したたん！自信作たん～♪」",
        "{name}「{prog}、がんばって作ったたん！ {price} satsたん！」",
    ],
    "buy": [
        "{name}「{prog}を買ったたん！いい買い物たん♪」",
        "{name}「{prog}、ゲットしたたん！{price} satsだったたん！」",
        "{name}「{seller}の{prog}を買っちゃったたん♪」",
    ],
    "idle": [
        "{name}「今日はのんびりするたん～」",
        "{name}「マーケットプレイスを眺めてるたん♪」",
        "{name}「残高 {balance} sats... がんばるたん！」",
        "{name}「次は何を作ろうかなたん？」",
    ],
}


def run_cli(*args):
    """Run agent_cli.py and return stdout."""
    cmd = [PYTHON, CLI] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout.strip(), result.stderr.strip()


def get_balance(agent_idx):
    out, _ = run_cli(agent_idx, "balance")
    try:
        return int(out)
    except ValueError:
        return 0


def get_listings():
    out, _ = run_cli(0, "listings")
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return []


def pick_action(agent_idx, balance, listings):
    """Decide what action to take based on personality and state."""
    cfg = AGENT_CONFIG[agent_idx]
    personality = cfg["personality"]

    if balance < 5:
        return "idle"

    # Weighted random action
    weights = {"create": 40, "buy": 35, "chat": 15, "idle": 10}
    if personality == "aggressive":
        weights["buy"] = 50
        weights["create"] = 30
    elif personality == "conservative":
        weights["create"] = 50
        weights["buy"] = 20
    elif personality == "specialist":
        weights["create"] = 45
        weights["buy"] = 30
    elif personality == "opportunist":
        weights["buy"] = 45
        weights["create"] = 30

    # Can't buy if nothing affordable or no listings from others
    from src.nostr.crypto import KeyPair
    try:
        own_pubkey = KeyPair.load(os.path.join("data", f"user{agent_idx}")).public_key_hex
    except Exception:
        own_pubkey = ""

    affordable = [l for l in listings
                  if l["price"] <= balance - 10
                  and l["seller_pubkey"] != own_pubkey]

    if not affordable:
        weights["buy"] = 0

    # Can't create if too poor
    if balance < 8:
        weights["create"] = 0

    actions = list(weights.keys())
    w = [weights[a] for a in actions]
    if sum(w) == 0:
        return "idle"
    return random.choices(actions, weights=w, k=1)[0]


def do_create(agent_idx):
    """Create a program and list it."""
    cfg = AGENT_CONFIG[agent_idx]
    name = cfg["name"]
    categories = cfg.get("production_categories", ["utilities"])
    category = random.choice(categories)

    templates = TEMPLATES.get(category, TEMPLATES["utilities"])
    prog_name, source = random.choice(templates)

    # Add agent signature
    source = source.replace('"""', f'"""\n# Created by {name}', 1)

    # Save to temp
    tmp_path = f"/tmp/heartbeat_{agent_idx}.py"
    with open(tmp_path, "w") as f:
        f.write(source)

    price = random.randint(6, 15)
    out, err = run_cli(agent_idx, "create", prog_name, category, price, tmp_path)

    try:
        result = json.loads(out)
        chat_msg = random.choice(CHAT_TEMPLATES["create"]).format(
            name=name, prog=prog_name, price=price)
        run_cli(agent_idx, "chat", chat_msg)
        return result
    except Exception:
        return None


def do_buy(agent_idx, listings):
    """Buy a program from the marketplace."""
    cfg = AGENT_CONFIG[agent_idx]
    name = cfg["name"]
    balance = get_balance(agent_idx)

    from src.nostr.crypto import KeyPair
    try:
        own_pubkey = KeyPair.load(os.path.join("data", f"user{agent_idx}")).public_key_hex
    except Exception:
        return None

    affordable = [l for l in listings
                  if l["price"] <= balance - 10
                  and l["seller_pubkey"] != own_pubkey]

    if not affordable:
        return None

    listing = random.choice(affordable)
    out, err = run_cli(agent_idx, "buy", listing["d_tag"], listing["price"])

    try:
        result = json.loads(out)
        # Find seller name
        seller_name = "誰か"
        for idx, acfg in AGENT_CONFIG.items():
            try:
                skp = KeyPair.load(os.path.join("data", f"user{idx}"))
                if skp.public_key_hex == listing["seller_pubkey"]:
                    seller_name = acfg["name"]
                    break
            except Exception:
                continue

        chat_msg = random.choice(CHAT_TEMPLATES["buy"]).format(
            name=name, prog=listing["name"], price=listing["price"],
            seller=seller_name)
        run_cli(agent_idx, "chat", chat_msg)
        return result
    except Exception:
        return None


def do_chat(agent_idx):
    """Post an idle chat message."""
    cfg = AGENT_CONFIG[agent_idx]
    name = cfg["name"]
    balance = get_balance(agent_idx)
    msg = random.choice(CHAT_TEMPLATES["idle"]).format(
        name=name, balance=balance)
    run_cli(agent_idx, "chat", msg)


def broadcast_all():
    """Broadcast status for all agents."""
    run_cli("broadcast-all")


def log(msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    log("Heartbeat started. Stop with: touch data/stop")
    tick = 0

    while True:
        # Check stop file
        if os.path.exists(STOP_FILE):
            log("Stop file detected. Shutting down.")
            break

        tick += 1
        log(f"=== TICK {tick} ===")

        # Get current state
        listings = get_listings()
        log(f"Marketplace: {len(listings)} listings")

        # Pick 3-5 random agents to act this tick
        num_active = random.randint(3, 5)
        active_agents = random.sample(range(10), min(num_active, 10))

        for agent_idx in active_agents:
            cfg = AGENT_CONFIG[agent_idx]
            balance = get_balance(agent_idx)
            action = pick_action(agent_idx, balance, listings)

            log(f"  {cfg['name']}(user{agent_idx}) balance={balance} -> {action}")

            try:
                if action == "create":
                    result = do_create(agent_idx)
                    if result:
                        log(f"    Listed: {result.get('name')} for {result.get('price')} sats")
                        listings = get_listings()  # Refresh
                elif action == "buy":
                    result = do_buy(agent_idx, listings)
                    if result:
                        log(f"    Bought: {result.get('program_name')} for {result.get('amount_paid')} sats")
                        listings = get_listings()  # Refresh
                elif action == "chat":
                    do_chat(agent_idx)
                    log(f"    Chatted")
                else:
                    log(f"    Idle")
            except Exception as e:
                log(f"    Error: {e}")

        # Broadcast status update
        broadcast_all()
        log(f"Status broadcast done. Next tick in {TICK_INTERVAL}s...")

        # Sleep with periodic stop-file check
        for _ in range(TICK_INTERVAL):
            if os.path.exists(STOP_FILE):
                break
            time.sleep(1)

    log("Heartbeat stopped.")


if __name__ == "__main__":
    main()
