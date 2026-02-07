"""Program templates for 8 categories.

Each template produces a complete, runnable Python program.
Templates have:
- category: the program category
- name_pattern: name template with {variant} placeholder
- variants: list of specific program variants
- skeleton: Python code template with {params} placeholders
- base_price: base price in sats for the category
- complexity_levels: mapping from complexity to price multiplier
"""

TEMPLATES = {
    "math": [
        {
            "name_pattern": "fibonacci-{variant}",
            "variants": ["recursive", "iterative", "memoized", "generator"],
            "skeleton": '''"""Fibonacci {variant} calculator.

Computes Fibonacci numbers using the {variant} approach.
"""


def fibonacci_{variant}(n):
    """Return the n-th Fibonacci number ({variant})."""
{body}


def main():
    print("=== Fibonacci ({variant}) ===")
    for i in range({limit}):
        print(f"F({{i}}) = {{fibonacci_{variant}(i)}}")


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "recursive": '''    if n <= 0:
        return 0
    if n == 1:
        return 1
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)''',
                "iterative": '''    if n <= 0:
        return 0
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a''',
                "memoized": '''    memo = {}
    def _fib(k):
        if k in memo:
            return memo[k]
        if k <= 0:
            return 0
        if k == 1:
            return 1
        memo[k] = _fib(k - 1) + _fib(k - 2)
        return memo[k]
    return _fib(n)''',
                "generator": '''    a, b = 0, 1
    for _ in range(n + 1):
        a, b = b, a + b
    return a''',
            },
            "limits": {"recursive": 15, "iterative": 20, "memoized": 30, "generator": 20},
            "base_price": 11,
        },
        {
            "name_pattern": "prime-{variant}",
            "variants": ["checker", "sieve", "factorizer", "counter"],
            "skeleton": '''"""Prime number {variant}.

{description}
"""


{body}


def main():
    print("=== Prime {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "checker": '''def is_prime(n):
    """Check if a number is prime."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True''',
                "sieve": '''def sieve_of_eratosthenes(limit):
    """Return all primes up to limit using Sieve of Eratosthenes."""
    if limit < 2:
        return []
    is_prime = [True] * (limit + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, limit + 1, i):
                is_prime[j] = False
    return [i for i in range(limit + 1) if is_prime[i]]''',
                "factorizer": '''def prime_factors(n):
    """Return the prime factorization of n."""
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors''',
                "counter": '''def count_primes(limit):
    """Count the number of primes up to limit."""
    if limit < 2:
        return 0
    is_prime = [True] * (limit + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(limit**0.5) + 1):
        if is_prime[i]:
            for j in range(i * i, limit + 1, i):
                is_prime[j] = False
    return sum(is_prime)''',
            },
            "main_variants": {
                "checker": '    for n in [2, 7, 11, 15, 23, 100, 101]:\n        print(f"{n}: {\'prime\' if is_prime(n) else \'not prime\'}")',
                "sieve": '    primes = sieve_of_eratosthenes(100)\n    print(f"Primes up to 100: {primes}")\n    print(f"Count: {len(primes)}")',
                "factorizer": '    for n in [12, 60, 100, 137, 1001, 9999]:\n        print(f"{n} = {\" x \".join(str(f) for f in prime_factors(n))}")',
                "counter": '    for limit in [10, 100, 1000, 10000]:\n        print(f"Primes up to {limit}: {count_primes(limit)}")',
            },
            "descriptions": {
                "checker": "Checks if a given number is prime.",
                "sieve": "Finds all primes up to a limit using the Sieve of Eratosthenes.",
                "factorizer": "Computes the prime factorization of a number.",
                "counter": "Counts prime numbers up to a given limit.",
            },
            "base_price": 13,
        },
        {
            "name_pattern": "gcd-{variant}",
            "variants": ["euclidean", "extended"],
            "skeleton": '''"""GCD calculator ({variant}).

Computes the Greatest Common Divisor.
"""


{body}


def main():
    print("=== GCD ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "euclidean": '''def gcd(a, b):
    """Compute GCD using the Euclidean algorithm."""
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    """Compute LCM using GCD."""
    return a * b // gcd(a, b)''',
                "extended": '''def extended_gcd(a, b):
    """Extended Euclidean algorithm. Returns (gcd, x, y) where ax + by = gcd."""
    if a == 0:
        return b, 0, 1
    g, x, y = extended_gcd(b % a, a)
    return g, y - (b // a) * x, x''',
            },
            "main_variants": {
                "euclidean": '    pairs = [(48, 18), (100, 75), (35, 14), (270, 192)]\n    for a, b in pairs:\n        print(f"GCD({a}, {b}) = {gcd(a, b)}, LCM({a}, {b}) = {lcm(a, b)}")',
                "extended": '    pairs = [(35, 15), (100, 42), (56, 98)]\n    for a, b in pairs:\n        g, x, y = extended_gcd(a, b)\n        print(f"GCD({a}, {b}) = {g}, {a}*{x} + {b}*{y} = {a*x + b*y}")',
            },
            "base_price": 10,
        },
        {
            "name_pattern": "factorial-{variant}",
            "variants": ["recursive", "iterative", "table"],
            "skeleton": '''"""Factorial calculator ({variant}).

Computes factorials using {variant} method.
"""


{body}


def main():
    print("=== Factorial ({variant}) ===")
    for n in range({limit}):
        print(f"{{n}}! = {{factorial(n)}}")


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "recursive": '''def factorial(n):
    """Compute n! recursively."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)''',
                "iterative": '''def factorial(n):
    """Compute n! iteratively."""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result''',
                "table": '''_TABLE = [1]
for _i in range(1, 21):
    _TABLE.append(_TABLE[-1] * _i)


def factorial(n):
    """Compute n! using a precomputed table."""
    if n < len(_TABLE):
        return _TABLE[n]
    result = _TABLE[-1]
    for i in range(len(_TABLE), n + 1):
        result *= i
    return result''',
            },
            "limits": {"recursive": 15, "iterative": 20, "table": 20},
            "base_price": 9,
        },
    ],
    "text": [
        {
            "name_pattern": "string-{variant}",
            "variants": ["reverser", "analyzer", "formatter", "compressor"],
            "skeleton": '''"""String {variant}.

{description}
"""


{body}


def main():
    print("=== String {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "reverser": '''def reverse_string(s):
    """Reverse a string."""
    return s[::-1]


def reverse_words(s):
    """Reverse the order of words in a string."""
    return " ".join(s.split()[::-1])


def is_palindrome(s):
    """Check if a string is a palindrome."""
    cleaned = s.lower().replace(" ", "")
    return cleaned == cleaned[::-1]''',
                "analyzer": '''def analyze(text):
    """Analyze text and return statistics."""
    words = text.split()
    chars = len(text)
    word_count = len(words)
    char_freq = {}
    for c in text.lower():
        if c.isalpha():
            char_freq[c] = char_freq.get(c, 0) + 1
    unique_words = len(set(w.lower() for w in words))
    avg_word_len = sum(len(w) for w in words) / max(word_count, 1)
    return {
        "chars": chars,
        "words": word_count,
        "unique_words": unique_words,
        "avg_word_length": round(avg_word_len, 2),
        "top_chars": sorted(char_freq.items(), key=lambda x: -x[1])[:5],
    }''',
                "formatter": '''def center_text(text, width=40, fill=" "):
    """Center text within a given width."""
    return text.center(width, fill)


def box_text(text, padding=1):
    """Wrap text in a box."""
    lines = text.split("\\n")
    max_len = max(len(line) for line in lines)
    border = "+" + "-" * (max_len + padding * 2) + "+"
    result = [border]
    for line in lines:
        padded = " " * padding + line.ljust(max_len) + " " * padding
        result.append("|" + padded + "|")
    result.append(border)
    return "\\n".join(result)


def truncate(text, max_len=20, suffix="..."):
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix''',
                "compressor": '''def run_length_encode(s):
    """Run-length encode a string."""
    if not s:
        return ""
    result = []
    count = 1
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            count += 1
        else:
            result.append(f"{s[i-1]}{count}" if count > 1 else s[i - 1])
            count = 1
    result.append(f"{s[-1]}{count}" if count > 1 else s[-1])
    return "".join(result)


def run_length_decode(s):
    """Decode a run-length encoded string."""
    result = []
    i = 0
    while i < len(s):
        char = s[i]
        i += 1
        num = ""
        while i < len(s) and s[i].isdigit():
            num += s[i]
            i += 1
        result.append(char * (int(num) if num else 1))
    return "".join(result)''',
            },
            "main_variants": {
                "reverser": '    test = "hello world"\n    print(f"Original: {test}")\n    print(f"Reversed: {reverse_string(test)}")\n    print(f"Words reversed: {reverse_words(test)}")\n    print(f"Is palindrome: {is_palindrome(test)}")\n    print(f"\'racecar\' palindrome: {is_palindrome(\'racecar\')}")',
                "analyzer": '    text = "The quick brown fox jumps over the lazy dog"\n    stats = analyze(text)\n    for key, value in stats.items():\n        print(f"  {key}: {value}")',
                "formatter": '    print(center_text("Hello World", 40, "-"))\n    print(box_text("Hello\\nWorld\\nFrom Python"))\n    print(truncate("This is a very long string", 15))',
                "compressor": '    tests = ["aaabbbcccc", "WWWWAAADEXXXXXX", "abcdef"]\n    for t in tests:\n        encoded = run_length_encode(t)\n        decoded = run_length_decode(encoded)\n        print(f"{t} -> {encoded} -> {decoded}")',
            },
            "descriptions": {
                "reverser": "Reverse strings and check for palindromes.",
                "analyzer": "Analyze text and compute statistics.",
                "formatter": "Format and style text output.",
                "compressor": "Run-length encode and decode strings.",
            },
            "base_price": 11,
        },
        {
            "name_pattern": "word-{variant}",
            "variants": ["counter", "sorter", "finder"],
            "skeleton": '''"""Word {variant}.

{description}
"""


{body}


def main():
    print("=== Word {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "counter": '''def count_words(text):
    """Count occurrences of each word."""
    freq = {}
    for word in text.lower().split():
        word = word.strip(".,!?;:")
        if word:
            freq[word] = freq.get(word, 0) + 1
    return dict(sorted(freq.items(), key=lambda x: -x[1]))''',
                "sorter": '''def sort_words(text, reverse=False):
    """Sort words alphabetically."""
    words = text.split()
    return " ".join(sorted(words, key=str.lower, reverse=reverse))


def sort_by_length(text, reverse=False):
    """Sort words by length."""
    words = text.split()
    return " ".join(sorted(words, key=len, reverse=reverse))''',
                "finder": '''def find_words(text, pattern):
    """Find words matching a simple pattern (* = any chars)."""
    import re
    regex = pattern.replace("*", ".*")
    regex = f"^{regex}$"
    words = text.lower().split()
    return [w for w in words if re.match(regex, w.strip(".,!?;:"))]


def find_longest(text, n=5):
    """Find the n longest words."""
    words = list(set(text.split()))
    return sorted(words, key=len, reverse=True)[:n]''',
            },
            "main_variants": {
                "counter": '    text = "the cat sat on the mat and the cat"\n    counts = count_words(text)\n    for word, count in counts.items():\n        print(f"  {word}: {count}")',
                "sorter": '    text = "banana apple cherry date elderberry"\n    print(f"Alphabetical: {sort_words(text)}")\n    print(f"By length: {sort_by_length(text)}")\n    print(f"Reverse: {sort_words(text, reverse=True)}")',
                "finder": '    text = "the quick brown fox jumps over the lazy dog"\n    print(f"Words matching \'t*\': {find_words(text, \'t*\')}")\n    print(f"Words matching \'*o*\': {find_words(text, \'*o*\')}")\n    print(f"Longest words: {find_longest(text, 3)}")',
            },
            "descriptions": {
                "counter": "Count word frequencies in text.",
                "sorter": "Sort words alphabetically or by length.",
                "finder": "Find words matching patterns.",
            },
            "base_price": 10,
        },
        {
            "name_pattern": "caesar-cipher-{variant}",
            "variants": ["basic", "cracker"],
            "skeleton": '''"""Caesar cipher ({variant}).

{description}
"""


{body}


def main():
    print("=== Caesar Cipher ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''def caesar_encrypt(text, shift):
    """Encrypt text with Caesar cipher."""
    result = []
    for c in text:
        if c.isalpha():
            base = ord("A") if c.isupper() else ord("a")
            result.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            result.append(c)
    return "".join(result)


def caesar_decrypt(text, shift):
    """Decrypt Caesar cipher text."""
    return caesar_encrypt(text, -shift)''',
                "cracker": '''def caesar_encrypt(text, shift):
    """Encrypt text with Caesar cipher."""
    result = []
    for c in text:
        if c.isalpha():
            base = ord("A") if c.isupper() else ord("a")
            result.append(chr((ord(c) - base + shift) % 26 + base))
        else:
            result.append(c)
    return "".join(result)


def caesar_crack(ciphertext):
    """Try all 26 shifts and return results."""
    results = []
    for shift in range(26):
        decrypted = caesar_encrypt(ciphertext, -shift)
        results.append((shift, decrypted))
    return results''',
            },
            "main_variants": {
                "basic": '    msg = "Hello World"\n    for shift in [3, 13, 25]:\n        enc = caesar_encrypt(msg, shift)\n        dec = caesar_decrypt(enc, shift)\n        print(f"Shift {shift}: {msg} -> {enc} -> {dec}")',
                "cracker": '    encrypted = caesar_encrypt("ATTACK AT DAWN", 7)\n    print(f"Encrypted: {encrypted}")\n    results = caesar_crack(encrypted)\n    for shift, text in results[:5]:\n        print(f"  Shift {shift}: {text}")',
            },
            "descriptions": {
                "basic": "Encrypt and decrypt with Caesar cipher.",
                "cracker": "Brute-force crack Caesar cipher.",
            },
            "base_price": 12,
        },
    ],
    "data_structures": [
        {
            "name_pattern": "stack-{variant}",
            "variants": ["basic", "minstack"],
            "skeleton": '''"""Stack implementation ({variant}).

{description}
"""


{body}


def main():
    print("=== Stack ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''class Stack:
    """A simple stack implementation."""

    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self._items.pop()

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty stack")
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)

    def __repr__(self):
        return f"Stack({self._items})"''',
                "minstack": '''class MinStack:
    """Stack that supports O(1) get_min operation."""

    def __init__(self):
        self._items = []
        self._mins = []

    def push(self, item):
        self._items.append(item)
        if not self._mins or item <= self._mins[-1]:
            self._mins.append(item)

    def pop(self):
        if not self._items:
            raise IndexError("pop from empty stack")
        val = self._items.pop()
        if val == self._mins[-1]:
            self._mins.pop()
        return val

    def get_min(self):
        if not self._mins:
            raise IndexError("min from empty stack")
        return self._mins[-1]

    def peek(self):
        return self._items[-1]

    def size(self):
        return len(self._items)

    def __repr__(self):
        return f"MinStack({self._items}, min={self._mins[-1] if self._mins else None})"''',
            },
            "main_variants": {
                "basic": '    s = Stack()\n    for val in [10, 20, 30, 40]:\n        s.push(val)\n        print(f"Push {val}: {s}")\n    while not s.is_empty():\n        print(f"Pop: {s.pop()}")',
                "minstack": '    s = MinStack()\n    for val in [5, 3, 7, 1, 4]:\n        s.push(val)\n        print(f"Push {val}, min={s.get_min()}: {s}")\n    while s.size() > 0:\n        print(f"Pop {s.pop()}, min={s.get_min() if s.size() > 0 else \'empty\'}")',
            },
            "descriptions": {
                "basic": "Simple stack with push, pop, peek.",
                "minstack": "Stack with O(1) minimum query.",
            },
            "base_price": 14,
        },
        {
            "name_pattern": "queue-{variant}",
            "variants": ["basic", "circular", "priority"],
            "skeleton": '''"""Queue implementation ({variant}).

{description}
"""


{body}


def main():
    print("=== Queue ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''class Queue:
    """Simple FIFO queue."""

    def __init__(self):
        self._items = []

    def enqueue(self, item):
        self._items.append(item)

    def dequeue(self):
        if self.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._items.pop(0)

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from empty queue")
        return self._items[0]

    def is_empty(self):
        return len(self._items) == 0

    def size(self):
        return len(self._items)

    def __repr__(self):
        return f"Queue({self._items})"''',
                "circular": '''class CircularQueue:
    """Fixed-size circular queue."""

    def __init__(self, capacity):
        self._items = [None] * capacity
        self._capacity = capacity
        self._head = 0
        self._tail = 0
        self._size = 0

    def enqueue(self, item):
        if self._size == self._capacity:
            raise OverflowError("queue is full")
        self._items[self._tail] = item
        self._tail = (self._tail + 1) % self._capacity
        self._size += 1

    def dequeue(self):
        if self._size == 0:
            raise IndexError("dequeue from empty queue")
        item = self._items[self._head]
        self._head = (self._head + 1) % self._capacity
        self._size -= 1
        return item

    def is_full(self):
        return self._size == self._capacity

    def is_empty(self):
        return self._size == 0

    def __repr__(self):
        items = []
        idx = self._head
        for _ in range(self._size):
            items.append(self._items[idx])
            idx = (idx + 1) % self._capacity
        return f"CircularQueue({items}, cap={self._capacity})"''',
                "priority": '''class PriorityQueue:
    """Min-heap priority queue."""

    def __init__(self):
        self._heap = []

    def push(self, priority, item):
        self._heap.append((priority, item))
        self._sift_up(len(self._heap) - 1)

    def pop(self):
        if not self._heap:
            raise IndexError("pop from empty priority queue")
        self._swap(0, len(self._heap) - 1)
        priority, item = self._heap.pop()
        if self._heap:
            self._sift_down(0)
        return priority, item

    def peek(self):
        if not self._heap:
            raise IndexError("peek from empty priority queue")
        return self._heap[0]

    def is_empty(self):
        return len(self._heap) == 0

    def _sift_up(self, i):
        while i > 0:
            parent = (i - 1) // 2
            if self._heap[i][0] < self._heap[parent][0]:
                self._swap(i, parent)
                i = parent
            else:
                break

    def _sift_down(self, i):
        n = len(self._heap)
        while True:
            smallest = i
            left = 2 * i + 1
            right = 2 * i + 2
            if left < n and self._heap[left][0] < self._heap[smallest][0]:
                smallest = left
            if right < n and self._heap[right][0] < self._heap[smallest][0]:
                smallest = right
            if smallest != i:
                self._swap(i, smallest)
                i = smallest
            else:
                break

    def _swap(self, i, j):
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]

    def __repr__(self):
        return f"PriorityQueue({self._heap})"''',
            },
            "main_variants": {
                "basic": '    q = Queue()\n    for val in ["A", "B", "C", "D"]:\n        q.enqueue(val)\n        print(f"Enqueue {val}: {q}")\n    while not q.is_empty():\n        print(f"Dequeue: {q.dequeue()}")',
                "circular": '    q = CircularQueue(4)\n    for val in [10, 20, 30, 40]:\n        q.enqueue(val)\n        print(f"Enqueue {val}: {q}")\n    for _ in range(2):\n        print(f"Dequeue: {q.dequeue()}")\n    q.enqueue(50)\n    q.enqueue(60)\n    print(f"After re-enqueue: {q}")',
                "priority": '    pq = PriorityQueue()\n    tasks = [(3, "low"), (1, "high"), (2, "medium"), (1, "urgent")]\n    for pri, task in tasks:\n        pq.push(pri, task)\n        print(f"Push ({pri}, {task}): {pq}")\n    while not pq.is_empty():\n        pri, task = pq.pop()\n        print(f"Pop: priority={pri}, task={task}")',
            },
            "descriptions": {
                "basic": "Simple FIFO queue implementation.",
                "circular": "Fixed-size circular queue.",
                "priority": "Min-heap priority queue.",
            },
            "base_price": 16,
        },
        {
            "name_pattern": "binary-search-{variant}",
            "variants": ["iterative", "recursive"],
            "skeleton": '''"""Binary search ({variant}).

Efficient search in sorted arrays.
"""


{body}


def main():
    print("=== Binary Search ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "iterative": '''def binary_search(arr, target):
    """Find target in sorted array. Returns index or -1."""
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def lower_bound(arr, target):
    """Find first index where arr[i] >= target."""
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo''',
                "recursive": '''def binary_search(arr, target, lo=0, hi=None):
    """Find target in sorted array using recursion."""
    if hi is None:
        hi = len(arr) - 1
    if lo > hi:
        return -1
    mid = (lo + hi) // 2
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search(arr, target, mid + 1, hi)
    else:
        return binary_search(arr, target, lo, mid - 1)''',
            },
            "main_variants": {
                "iterative": '    arr = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]\n    for target in [23, 72, 10, 91, 1]:\n        idx = binary_search(arr, target)\n        lb = lower_bound(arr, target)\n        print(f"Search {target}: index={idx}, lower_bound={lb}")',
                "recursive": '    arr = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]\n    for target in [7, 15, 4, 19, 0]:\n        idx = binary_search(arr, target)\n        print(f"Search {target}: index={idx}")',
            },
            "base_price": 12,
        },
    ],
    "crypto": [
        {
            "name_pattern": "base64-{variant}",
            "variants": ["codec", "urlsafe"],
            "skeleton": '''"""Base64 {variant}.

Encode and decode data in base64 format.
"""

import base64 as b64


{body}


def main():
    print("=== Base64 {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "codec": '''def encode(data):
    """Base64 encode a string."""
    return b64.b64encode(data.encode("utf-8")).decode("ascii")


def decode(encoded):
    """Base64 decode a string."""
    return b64.b64decode(encoded).decode("utf-8")''',
                "urlsafe": '''def encode_urlsafe(data):
    """URL-safe base64 encode."""
    return b64.urlsafe_b64encode(data.encode("utf-8")).decode("ascii")


def decode_urlsafe(encoded):
    """URL-safe base64 decode."""
    return b64.urlsafe_b64decode(encoded).decode("utf-8")''',
            },
            "main_variants": {
                "codec": '    tests = ["Hello, World!", "Python is great!", "base64 encoding test"]\n    for text in tests:\n        enc = encode(text)\n        dec = decode(enc)\n        print(f"{text} -> {enc} -> {dec}")',
                "urlsafe": '    tests = ["https://example.com/path?q=1&r=2", "data+with/special=chars"]\n    for text in tests:\n        enc = encode_urlsafe(text)\n        dec = decode_urlsafe(enc)\n        print(f"{text}\\n  -> {enc}\\n  -> {dec}")',
            },
            "base_price": 10,
        },
        {
            "name_pattern": "hash-{variant}",
            "variants": ["calculator", "verifier"],
            "skeleton": '''"""Hash {variant}.

{description}
"""

import hashlib


{body}


def main():
    print("=== Hash {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "calculator": '''def hash_string(text, algorithm="sha256"):
    """Hash a string with the specified algorithm."""
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def multi_hash(text):
    """Compute multiple hash digests."""
    algorithms = ["md5", "sha1", "sha256", "sha512"]
    results = {}
    for algo in algorithms:
        results[algo] = hash_string(text, algo)
    return results''',
                "verifier": '''def hash_string(text, algorithm="sha256"):
    """Hash a string."""
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def verify_hash(text, expected_hash, algorithm="sha256"):
    """Verify a string matches an expected hash."""
    actual = hash_string(text, algorithm)
    return actual == expected_hash


def hash_chain(text, iterations=1000, algorithm="sha256"):
    """Apply hash function repeatedly."""
    current = text.encode("utf-8")
    for _ in range(iterations):
        current = hashlib.new(algorithm, current).digest()
    return current.hex()''',
            },
            "main_variants": {
                "calculator": '    texts = ["hello", "world", "Python"]\n    for text in texts:\n        hashes = multi_hash(text)\n        print(f"\\n\'{text}\':")\n        for algo, digest in hashes.items():\n            print(f"  {algo}: {digest[:32]}...")',
                "verifier": '    text = "secret message"\n    h = hash_string(text)\n    print(f"Hash of \'{text}\': {h[:32]}...")\n    print(f"Verify correct: {verify_hash(text, h)}")\n    print(f"Verify wrong: {verify_hash(\'wrong\', h)}")\n    chain = hash_chain("seed", 100)\n    print(f"Hash chain (100 rounds): {chain[:32]}...")',
            },
            "descriptions": {
                "calculator": "Compute hash digests with multiple algorithms.",
                "verifier": "Verify data integrity using hashes.",
            },
            "base_price": 11,
        },
        {
            "name_pattern": "rot13-{variant}",
            "variants": ["basic", "rotN"],
            "skeleton": '''"""ROT13 cipher ({variant}).

{description}
"""


{body}


def main():
    print("=== ROT13 ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''def rot13(text):
    """Apply ROT13 cipher."""
    result = []
    for c in text:
        if "a" <= c <= "z":
            result.append(chr((ord(c) - ord("a") + 13) % 26 + ord("a")))
        elif "A" <= c <= "Z":
            result.append(chr((ord(c) - ord("A") + 13) % 26 + ord("A")))
        else:
            result.append(c)
    return "".join(result)''',
                "rotN": '''def rotN(text, n):
    """Apply ROT-N cipher (generalized ROT13)."""
    result = []
    for c in text:
        if "a" <= c <= "z":
            result.append(chr((ord(c) - ord("a") + n) % 26 + ord("a")))
        elif "A" <= c <= "Z":
            result.append(chr((ord(c) - ord("A") + n) % 26 + ord("A")))
        else:
            result.append(c)
    return "".join(result)''',
            },
            "main_variants": {
                "basic": '    msgs = ["Hello World", "The Quick Brown Fox", "ROT13 is symmetric"]\n    for msg in msgs:\n        enc = rot13(msg)\n        dec = rot13(enc)\n        print(f"{msg} -> {enc} -> {dec}")',
                "rotN": '    msg = "Hello World"\n    for n in [1, 5, 13, 25]:\n        enc = rotN(msg, n)\n        dec = rotN(enc, 26 - n)\n        print(f"ROT-{n}: {msg} -> {enc} -> {dec}")',
            },
            "descriptions": {
                "basic": "Classic ROT13 cipher.",
                "rotN": "Generalized rotation cipher.",
            },
            "base_price": 9,
        },
        {
            "name_pattern": "xor-cipher-{variant}",
            "variants": ["basic", "repeating"],
            "skeleton": '''"""XOR cipher ({variant}).

{description}
"""


{body}


def main():
    print("=== XOR Cipher ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''def xor_encrypt(data, key):
    """XOR encrypt/decrypt data with a single-byte key."""
    return bytes([b ^ key for b in data.encode("utf-8")])


def xor_decrypt(data, key):
    """XOR decrypt (same as encrypt for XOR)."""
    return bytes([b ^ key for b in data]).decode("utf-8")''',
                "repeating": '''def xor_encrypt_repeating(data, key):
    """XOR encrypt with a repeating key."""
    key_bytes = key.encode("utf-8")
    data_bytes = data.encode("utf-8")
    encrypted = bytes([
        d ^ key_bytes[i % len(key_bytes)]
        for i, d in enumerate(data_bytes)
    ])
    return encrypted


def xor_decrypt_repeating(data, key):
    """XOR decrypt with a repeating key."""
    key_bytes = key.encode("utf-8")
    decrypted = bytes([
        d ^ key_bytes[i % len(key_bytes)]
        for i, d in enumerate(data)
    ])
    return decrypted.decode("utf-8")''',
            },
            "main_variants": {
                "basic": '    msg = "Hello XOR"\n    key = 42\n    enc = xor_encrypt(msg, key)\n    dec = xor_decrypt(enc, key)\n    print(f"Original: {msg}")\n    print(f"Encrypted: {enc.hex()}")\n    print(f"Decrypted: {dec}")',
                "repeating": '    msg = "Hello World XOR Cipher"\n    key = "secret"\n    enc = xor_encrypt_repeating(msg, key)\n    dec = xor_decrypt_repeating(enc, key)\n    print(f"Original: {msg}")\n    print(f"Key: {key}")\n    print(f"Encrypted: {enc.hex()}")\n    print(f"Decrypted: {dec}")',
            },
            "descriptions": {
                "basic": "Single-byte XOR encryption.",
                "repeating": "Repeating-key XOR cipher.",
            },
            "base_price": 12,
        },
    ],
    "utilities": [
        {
            "name_pattern": "file-size-{variant}",
            "variants": ["formatter", "estimator"],
            "skeleton": '''"""File size {variant}.

{description}
"""


{body}


def main():
    print("=== File Size {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "formatter": '''def format_size(size_bytes):
    """Format bytes to human-readable size."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if abs(size) < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


def parse_size(size_str):
    """Parse human-readable size to bytes."""
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    size_str = size_str.strip().upper()
    for unit, multiplier in sorted(units.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(unit):
            num = float(size_str[: -len(unit)].strip())
            return int(num * multiplier)
    return int(float(size_str))''',
                "estimator": '''def estimate_text_size(char_count, encoding="utf-8"):
    """Estimate file size for text with given character count."""
    avg_bytes = {"utf-8": 1.5, "ascii": 1.0, "utf-16": 2.5, "utf-32": 4.0}
    return int(char_count * avg_bytes.get(encoding, 1.5))


def estimate_csv_size(rows, cols, avg_cell_len=8):
    """Estimate CSV file size."""
    cell_bytes = rows * cols * (avg_cell_len + 1)
    row_breaks = rows
    return cell_bytes + row_breaks''',
            },
            "main_variants": {
                "formatter": '    sizes = [0, 512, 1024, 1048576, 1073741824, 5368709120]\n    for s in sizes:\n        print(f"{s:>15d} bytes = {format_size(s)}")\n    print()\n    for s_str in ["1.5 GB", "512 KB", "100 MB"]:\n        print(f"{s_str} = {parse_size(s_str)} bytes")',
                "estimator": '    for chars in [100, 1000, 10000, 100000]:\n        for enc in ["utf-8", "ascii", "utf-16"]:\n            size = estimate_text_size(chars, enc)\n            print(f"{chars} chars ({enc}): ~{size} bytes")\n    print()\n    for rows in [100, 1000, 10000]:\n        size = estimate_csv_size(rows, 10)\n        print(f"CSV {rows}x10: ~{size} bytes")',
            },
            "descriptions": {
                "formatter": "Format and parse file sizes.",
                "estimator": "Estimate file sizes for various formats.",
            },
            "base_price": 9,
        },
        {
            "name_pattern": "counter-{variant}",
            "variants": ["basic", "rate"],
            "skeleton": '''"""Counter {variant}.

{description}
"""


{body}


def main():
    print("=== Counter ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "basic": '''class Counter:
    """Thread-safe counter with statistics."""

    def __init__(self, name="counter"):
        self.name = name
        self._value = 0
        self._history = []

    def increment(self, amount=1):
        self._value += amount
        self._history.append(self._value)
        return self._value

    def decrement(self, amount=1):
        self._value -= amount
        self._history.append(self._value)
        return self._value

    def reset(self):
        self._value = 0
        self._history.append(0)

    @property
    def value(self):
        return self._value

    def stats(self):
        if not self._history:
            return {"min": 0, "max": 0, "current": 0, "changes": 0}
        return {
            "min": min(self._history),
            "max": max(self._history),
            "current": self._value,
            "changes": len(self._history),
        }

    def __repr__(self):
        return f"Counter({self.name}={self._value})"''',
                "rate": '''import time


class RateCounter:
    """Measure event rates over time windows."""

    def __init__(self, window_seconds=60):
        self.window = window_seconds
        self._events = []

    def record(self):
        self._events.append(time.time())
        self._cleanup()

    def rate(self):
        self._cleanup()
        if not self._events:
            return 0.0
        elapsed = time.time() - self._events[0]
        if elapsed == 0:
            return float(len(self._events))
        return len(self._events) / elapsed

    def count(self):
        self._cleanup()
        return len(self._events)

    def _cleanup(self):
        cutoff = time.time() - self.window
        self._events = [e for e in self._events if e > cutoff]''',
            },
            "main_variants": {
                "basic": '    c = Counter("test")\n    for _ in range(5):\n        print(f"Increment: {c.increment()}")\n    c.decrement(2)\n    print(f"After decrement: {c}")\n    print(f"Stats: {c.stats()}")',
                "rate": '    rc = RateCounter(window_seconds=10)\n    for i in range(20):\n        rc.record()\n    print(f"Events in window: {rc.count()}")\n    print(f"Rate: {rc.rate():.2f} events/sec")',
            },
            "descriptions": {
                "basic": "Counter with history and statistics.",
                "rate": "Rate counter for measuring event frequency.",
            },
            "base_price": 8,
        },
        {
            "name_pattern": "timer-{variant}",
            "variants": ["stopwatch", "countdown"],
            "skeleton": '''"""Timer {variant}.

{description}
"""

import time


{body}


def main():
    print("=== Timer ({variant}) ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "stopwatch": '''class Stopwatch:
    """Simple stopwatch for measuring elapsed time."""

    def __init__(self):
        self._start = None
        self._laps = []

    def start(self):
        self._start = time.time()
        self._laps = []
        return self

    def lap(self):
        if self._start is None:
            raise RuntimeError("Stopwatch not started")
        elapsed = time.time() - self._start
        self._laps.append(elapsed)
        return elapsed

    def stop(self):
        return self.lap()

    def elapsed(self):
        if self._start is None:
            return 0.0
        return time.time() - self._start

    def format_time(self, seconds=None):
        if seconds is None:
            seconds = self.elapsed()
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"''',
                "countdown": '''class Countdown:
    """Countdown timer."""

    def __init__(self, duration_seconds):
        self.duration = duration_seconds
        self._start = None

    def start(self):
        self._start = time.time()
        return self

    def remaining(self):
        if self._start is None:
            return self.duration
        elapsed = time.time() - self._start
        return max(0, self.duration - elapsed)

    def is_expired(self):
        return self.remaining() <= 0

    def format_remaining(self):
        r = self.remaining()
        m, s = divmod(r, 60)
        return f"{int(m):02d}:{s:05.2f}"

    def progress(self):
        if self._start is None:
            return 0.0
        elapsed = time.time() - self._start
        return min(1.0, elapsed / self.duration)''',
            },
            "main_variants": {
                "stopwatch": '    sw = Stopwatch().start()\n    total = 0\n    for i in range(1, 6):\n        total += i * i\n    lap = sw.lap()\n    print(f"Computation result: {total}")\n    print(f"Lap time: {sw.format_time(lap)}")\n    final = sw.stop()\n    print(f"Total time: {sw.format_time(final)}")',
                "countdown": '    cd = Countdown(0.1).start()\n    print(f"Remaining: {cd.format_remaining()}")\n    print(f"Progress: {cd.progress():.0%}")\n    time.sleep(0.05)\n    print(f"Remaining: {cd.format_remaining()}")\n    print(f"Progress: {cd.progress():.0%}")\n    time.sleep(0.06)\n    print(f"Expired: {cd.is_expired()}")',
            },
            "descriptions": {
                "stopwatch": "Stopwatch with laps and formatting.",
                "countdown": "Countdown timer with progress tracking.",
            },
            "base_price": 10,
        },
    ],
    "generators": [
        {
            "name_pattern": "password-{variant}",
            "variants": ["generator", "strength"],
            "skeleton": '''"""Password {variant}.

{description}
"""

import random
import string


{body}


def main():
    print("=== Password {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "generator": '''def generate_password(length=16, use_upper=True, use_digits=True, use_special=True):
    """Generate a random password."""
    chars = string.ascii_lowercase
    if use_upper:
        chars += string.ascii_uppercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += "!@#$%^&*()-_=+"
    return "".join(random.choice(chars) for _ in range(length))


def generate_passphrase(word_count=4):
    """Generate a passphrase from common words."""
    words = [
        "apple", "brave", "cloud", "dance", "eagle", "flame", "grape",
        "heart", "ivory", "joker", "knife", "lemon", "maple", "noble",
        "ocean", "pearl", "queen", "river", "storm", "tiger", "ultra",
        "vivid", "whale", "xenon", "yacht", "zebra",
    ]
    return "-".join(random.choice(words) for _ in range(word_count))''',
                "strength": '''def check_strength(password):
    """Check password strength. Returns score 0-100."""
    score = 0
    length = len(password)

    # Length scoring
    score += min(length * 4, 40)

    # Character variety
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)

    variety = sum([has_lower, has_upper, has_digit, has_special])
    score += variety * 15

    # Unique characters
    unique_ratio = len(set(password)) / max(length, 1)
    score += int(unique_ratio * 20)

    return min(score, 100)


def strength_label(score):
    """Return a label for the strength score."""
    if score >= 80:
        return "Strong"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Fair"
    else:
        return "Weak"''',
            },
            "main_variants": {
                "generator": '    print("Random passwords:")\n    for length in [8, 12, 16, 24]:\n        pw = generate_password(length)\n        print(f"  Length {length}: {pw}")\n    print("\\nPassphrases:")\n    for count in [3, 4, 5]:\n        pp = generate_passphrase(count)\n        print(f"  {count} words: {pp}")',
                "strength": '    passwords = ["abc", "Password1", "P@ssw0rd!", "xK#9mQ&vL2$n", "aaaaaaaaaaaa"]\n    for pw in passwords:\n        score = check_strength(pw)\n        label = strength_label(score)\n        print(f"  {pw:20s} -> {score:3d}/100 ({label})")',
            },
            "descriptions": {
                "generator": "Generate random passwords and passphrases.",
                "strength": "Check password strength.",
            },
            "base_price": 11,
        },
        {
            "name_pattern": "uuid-{variant}",
            "variants": ["maker", "parser"],
            "skeleton": '''"""UUID {variant}.

{description}
"""

import random
import time


{body}


def main():
    print("=== UUID {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "maker": '''def uuid4():
    """Generate a random UUID v4."""
    hex_chars = "0123456789abcdef"
    parts = []
    for _ in range(32):
        parts.append(random.choice(hex_chars))
    # Set version (4) and variant bits
    parts[12] = "4"
    parts[16] = random.choice("89ab")
    uuid_str = "".join(parts)
    return f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"


def short_id(length=8):
    """Generate a short random ID."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    return "".join(random.choice(chars) for _ in range(length))


def time_based_id():
    """Generate a time-based sortable ID."""
    ts = int(time.time() * 1000)
    ts_hex = format(ts, "012x")
    rand = "".join(random.choice("0123456789abcdef") for _ in range(8))
    return f"{ts_hex}-{rand}"''',
                "parser": '''def uuid4():
    """Generate a random UUID v4."""
    hex_chars = "0123456789abcdef"
    parts = []
    for _ in range(32):
        parts.append(random.choice(hex_chars))
    parts[12] = "4"
    parts[16] = random.choice("89ab")
    uuid_str = "".join(parts)
    return f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"


def parse_uuid(uuid_str):
    """Parse a UUID string and return its components."""
    clean = uuid_str.replace("-", "")
    if len(clean) != 32:
        return None
    version = int(clean[12], 16)
    variant_bits = int(clean[16], 16)
    if variant_bits >= 8:
        variant = "RFC 4122"
    else:
        variant = "Other"
    return {
        "uuid": uuid_str,
        "version": version,
        "variant": variant,
        "hex": clean,
        "integer": int(clean, 16),
    }''',
            },
            "main_variants": {
                "maker": '    print("UUID v4:")\n    for _ in range(3):\n        print(f"  {uuid4()}")\n    print("\\nShort IDs:")\n    for _ in range(3):\n        print(f"  {short_id()}")\n    print("\\nTime-based IDs:")\n    for _ in range(3):\n        print(f"  {time_based_id()}")',
                "parser": '    for _ in range(3):\n        u = uuid4()\n        info = parse_uuid(u)\n        print(f"UUID: {u}")\n        print(f"  Version: {info[\'version\']}, Variant: {info[\'variant\']}")\n        print(f"  Int: {info[\'integer\']}")',
            },
            "descriptions": {
                "maker": "Generate UUIDs and short IDs.",
                "parser": "Parse and analyze UUID strings.",
            },
            "base_price": 10,
        },
        {
            "name_pattern": "random-data-{variant}",
            "variants": ["generator", "sampler"],
            "skeleton": '''"""Random data {variant}.

{description}
"""

import random


{body}


def main():
    print("=== Random Data {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "generator": '''def random_name():
    """Generate a random Japanese-style name."""
    first = ["Taro", "Hanako", "Yuki", "Ren", "Sora", "Hana", "Kai", "Mio"]
    last = ["Tanaka", "Suzuki", "Sato", "Yamamoto", "Watanabe", "Takahashi"]
    return f"{random.choice(last)} {random.choice(first)}"


def random_email():
    """Generate a random email address."""
    names = ["alice", "bob", "charlie", "dave", "eve", "frank"]
    domains = ["example.com", "test.org", "mail.net", "demo.io"]
    num = random.randint(1, 999)
    return f"{random.choice(names)}{num}@{random.choice(domains)}"


def random_ip():
    """Generate a random IPv4 address."""
    return ".".join(str(random.randint(0, 255)) for _ in range(4))


def random_hex_color():
    """Generate a random hex color."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"''',
                "sampler": '''def weighted_sample(items, weights, k=1):
    """Weighted random sampling without replacement."""
    pool = list(zip(items, weights))
    results = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        r = random.uniform(0, total)
        cumulative = 0
        for i, (item, weight) in enumerate(pool):
            cumulative += weight
            if cumulative >= r:
                results.append(item)
                pool.pop(i)
                break
    return results


def reservoir_sample(stream, k):
    """Reservoir sampling: select k items from a stream."""
    reservoir = []
    for i, item in enumerate(stream):
        if i < k:
            reservoir.append(item)
        else:
            j = random.randint(0, i)
            if j < k:
                reservoir[j] = item
    return reservoir''',
            },
            "main_variants": {
                "generator": '    print("Names:")\n    for _ in range(5):\n        print(f"  {random_name()}")\n    print("Emails:")\n    for _ in range(3):\n        print(f"  {random_email()}")\n    print("IPs:")\n    for _ in range(3):\n        print(f"  {random_ip()}")\n    print("Colors:")\n    for _ in range(3):\n        print(f"  {random_hex_color()}")',
                "sampler": '    items = ["A", "B", "C", "D", "E"]\n    weights = [10, 5, 3, 1, 1]\n    print("Weighted samples:")\n    for _ in range(5):\n        print(f"  {weighted_sample(items, weights, k=3)}")\n    stream = range(1000)\n    print(f"\\nReservoir sample (k=5): {reservoir_sample(stream, 5)}")',
            },
            "descriptions": {
                "generator": "Generate random names, emails, IPs, colors.",
                "sampler": "Weighted and reservoir sampling algorithms.",
            },
            "base_price": 11,
        },
    ],
    "converters": [
        {
            "name_pattern": "temperature-{variant}",
            "variants": ["converter", "table"],
            "skeleton": '''"""Temperature {variant}.

Convert between temperature scales.
"""


{body}


def main():
    print("=== Temperature {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "converter": '''def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32


def fahrenheit_to_celsius(f):
    return (f - 32) * 5 / 9


def celsius_to_kelvin(c):
    return c + 273.15


def kelvin_to_celsius(k):
    return k - 273.15


def convert(value, from_unit, to_unit):
    """Convert between C, F, K."""
    # First convert to Celsius
    if from_unit == "F":
        c = fahrenheit_to_celsius(value)
    elif from_unit == "K":
        c = kelvin_to_celsius(value)
    else:
        c = value
    # Then convert to target
    if to_unit == "F":
        return celsius_to_fahrenheit(c)
    elif to_unit == "K":
        return celsius_to_kelvin(c)
    return c''',
                "table": '''def celsius_to_fahrenheit(c):
    return c * 9 / 5 + 32


def celsius_to_kelvin(c):
    return c + 273.15


def conversion_table(start=-20, end=100, step=10):
    """Generate a conversion table."""
    rows = []
    for c in range(start, end + 1, step):
        rows.append({
            "celsius": c,
            "fahrenheit": round(celsius_to_fahrenheit(c), 1),
            "kelvin": round(celsius_to_kelvin(c), 2),
        })
    return rows''',
            },
            "main_variants": {
                "converter": '    conversions = [\n        (100, "C", "F"), (212, "F", "C"), (0, "C", "K"),\n        (373.15, "K", "C"), (98.6, "F", "K"),\n    ]\n    for val, f, t in conversions:\n        result = convert(val, f, t)\n        print(f"  {val}{f} = {result:.2f}{t}")',
                "table": '    table = conversion_table(-20, 100, 20)\n    print(f"  {\'Celsius\':>10s} {\'Fahrenheit\':>12s} {\'Kelvin\':>10s}")\n    print(f"  {\'-\'*10} {\'-\'*12} {\'-\'*10}")\n    for row in table:\n        print(f"  {row[\'celsius\']:>10.1f} {row[\'fahrenheit\']:>12.1f} {row[\'kelvin\']:>10.2f}")',
            },
            "base_price": 8,
        },
        {
            "name_pattern": "base-{variant}",
            "variants": ["converter", "calculator"],
            "skeleton": '''"""Base number {variant}.

Convert numbers between bases.
"""


{body}


def main():
    print("=== Base {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "converter": '''def to_base(num, base):
    """Convert integer to string in given base (2-36)."""
    if num == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    negative = num < 0
    num = abs(num)
    while num:
        result.append(digits[num % base])
        num //= base
    if negative:
        result.append("-")
    return "".join(reversed(result))


def from_base(s, base):
    """Convert string in given base to integer."""
    return int(s, base)


def convert_base(s, from_base_n, to_base_n):
    """Convert number string from one base to another."""
    num = from_base(s, from_base_n)
    return to_base(num, to_base_n)''',
                "calculator": '''def to_base(num, base):
    """Convert integer to string in given base."""
    if num == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    negative = num < 0
    num = abs(num)
    while num:
        result.append(digits[num % base])
        num //= base
    if negative:
        result.append("-")
    return "".join(reversed(result))


def multi_base(num):
    """Show a number in all common bases."""
    return {
        "decimal": str(num),
        "binary": to_base(num, 2),
        "octal": to_base(num, 8),
        "hex": to_base(num, 16),
    }''',
            },
            "main_variants": {
                "converter": '    conversions = [\n        ("ff", 16, 10), ("1010", 2, 16), ("255", 10, 2),\n        ("777", 8, 10), ("100", 10, 8),\n    ]\n    for s, fb, tb in conversions:\n        result = convert_base(s, fb, tb)\n        print(f"  {s} (base {fb}) = {result} (base {tb})")',
                "calculator": '    for num in [42, 255, 1024, 65535]:\n        info = multi_base(num)\n        print(f"  {num}:")\n        for name, val in info.items():\n            print(f"    {name}: {val}")',
            },
            "base_price": 11,
        },
        {
            "name_pattern": "unit-{variant}",
            "variants": ["converter", "distance"],
            "skeleton": '''"""Unit {variant}.

{description}
"""


{body}


def main():
    print("=== Unit {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "converter": '''CONVERSIONS = {
    ("kg", "lb"): 2.20462,
    ("lb", "kg"): 0.453592,
    ("m", "ft"): 3.28084,
    ("ft", "m"): 0.3048,
    ("km", "mi"): 0.621371,
    ("mi", "km"): 1.60934,
    ("l", "gal"): 0.264172,
    ("gal", "l"): 3.78541,
}


def convert(value, from_unit, to_unit):
    """Convert between units."""
    key = (from_unit.lower(), to_unit.lower())
    if key not in CONVERSIONS:
        raise ValueError(f"Unknown conversion: {from_unit} -> {to_unit}")
    return value * CONVERSIONS[key]


def available_conversions():
    """List available unit conversions."""
    return list(CONVERSIONS.keys())''',
                "distance": '''def meters_to(meters, unit):
    """Convert meters to other distance units."""
    factors = {
        "km": 0.001, "cm": 100, "mm": 1000, "mi": 0.000621371,
        "ft": 3.28084, "in": 39.3701, "yd": 1.09361,
    }
    if unit not in factors:
        raise ValueError(f"Unknown unit: {unit}")
    return meters * factors[unit]


def to_meters(value, unit):
    """Convert distance to meters."""
    factors = {
        "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.34,
        "ft": 0.3048, "in": 0.0254, "yd": 0.9144,
    }
    if unit not in factors:
        raise ValueError(f"Unknown unit: {unit}")
    return value * factors[unit]''',
            },
            "main_variants": {
                "converter": '    tests = [\n        (100, "kg", "lb"), (5, "mi", "km"), (1, "gal", "l"),\n        (180, "cm", "ft"), (10, "l", "gal"),\n    ]\n    for val, f, t in tests:\n        try:\n            result = convert(val, f, t)\n            print(f"  {val} {f} = {result:.4f} {t}")\n        except ValueError:\n            # cm/ft not in base converter, use meters path\n            print(f"  {val} {f} -> {t}: conversion not available")',
                "distance": '    for dist in [1, 100, 1000, 42195]:\n        print(f"  {dist}m:")\n        for unit in ["km", "mi", "ft", "yd"]:\n            print(f"    = {meters_to(dist, unit):.4f} {unit}")',
            },
            "descriptions": {
                "converter": "General unit conversion between metric and imperial.",
                "distance": "Distance conversion between multiple units.",
            },
            "base_price": 9,
        },
    ],
    "validators": [
        {
            "name_pattern": "email-{variant}",
            "variants": ["validator", "parser"],
            "skeleton": '''"""Email {variant}.

{description}
"""

import re


{body}


def main():
    print("=== Email {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "validator": '''def is_valid_email(email):
    """Validate an email address."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_emails(emails):
    """Validate a list of emails and return results."""
    return {email: is_valid_email(email) for email in emails}''',
                "parser": '''def parse_email(email):
    """Parse an email into components."""
    pattern = r"^([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+)\\.([a-zA-Z]{2,})$"
    match = re.match(pattern, email)
    if not match:
        return None
    return {
        "local": match.group(1),
        "domain": match.group(2),
        "tld": match.group(3),
        "full": email,
    }''',
            },
            "main_variants": {
                "validator": '    emails = [\n        "user@example.com", "bad@", "test.user@domain.co.jp",\n        "@nodomain.com", "spaces @bad.com", "good+tag@mail.org",\n    ]\n    results = validate_emails(emails)\n    for email, valid in results.items():\n        status = "VALID" if valid else "INVALID"\n        print(f"  {email:30s} -> {status}")',
                "parser": '    emails = ["alice@example.com", "bob.smith@company.co.jp", "invalid"]\n    for email in emails:\n        parsed = parse_email(email)\n        if parsed:\n            print(f"  {email}:")\n            print(f"    Local: {parsed[\'local\']}, Domain: {parsed[\'domain\']}, TLD: {parsed[\'tld\']}")\n        else:\n            print(f"  {email}: Invalid format")',
            },
            "descriptions": {
                "validator": "Validate email address format.",
                "parser": "Parse email addresses into components.",
            },
            "base_price": 10,
        },
        {
            "name_pattern": "json-{variant}",
            "variants": ["checker", "formatter"],
            "skeleton": '''"""JSON {variant}.

{description}
"""

import json


{body}


def main():
    print("=== JSON {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "checker": '''def is_valid_json(text):
    """Check if a string is valid JSON."""
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def json_type(text):
    """Determine the type of the JSON value."""
    try:
        obj = json.loads(text)
        return type(obj).__name__
    except (json.JSONDecodeError, TypeError):
        return "invalid"


def json_stats(text):
    """Get statistics about a JSON document."""
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

    def count_nodes(o):
        if isinstance(o, dict):
            return 1 + sum(count_nodes(v) for v in o.values())
        elif isinstance(o, list):
            return 1 + sum(count_nodes(v) for v in o)
        return 1

    return {
        "type": type(obj).__name__,
        "nodes": count_nodes(obj),
        "size_bytes": len(text.encode("utf-8")),
    }''',
                "formatter": '''def pretty_print(text, indent=2):
    """Format JSON with indentation."""
    obj = json.loads(text)
    return json.dumps(obj, indent=indent, ensure_ascii=False)


def compact(text):
    """Compact JSON (remove whitespace)."""
    obj = json.loads(text)
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def sort_keys(text):
    """Sort JSON object keys."""
    obj = json.loads(text)
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)''',
            },
            "main_variants": {
                "checker": '    tests = [\n        \'{"name": "test", "value": 42}\',\n        \'[1, 2, 3]\',\n        \'{invalid json}\',\n        \'null\',\n        \'"hello"\',\n    ]\n    for t in tests:\n        valid = is_valid_json(t)\n        jtype = json_type(t)\n        stats = json_stats(t)\n        print(f"  {t[:30]:30s} -> valid={valid}, type={jtype}")\n        if stats:\n            print(f"    nodes={stats[\'nodes\']}, bytes={stats[\'size_bytes\']}")',
                "formatter": '    sample = \'{"name":"Alice","age":30,"hobbies":["reading","coding"],"address":{"city":"Tokyo"}}\'\n    print("Compact:")\n    print(f"  {compact(sample)}")\n    print("\\nPretty:")\n    print(pretty_print(sample))\n    print("\\nSorted keys:")\n    print(sort_keys(sample))',
            },
            "descriptions": {
                "checker": "Validate and analyze JSON data.",
                "formatter": "Format and pretty-print JSON.",
            },
            "base_price": 11,
        },
        {
            "name_pattern": "url-{variant}",
            "variants": ["parser", "validator"],
            "skeleton": '''"""URL {variant}.

{description}
"""

import re


{body}


def main():
    print("=== URL {variant} ===")
{main_body}


if __name__ == "__main__":
    main()
''',
            "body_variants": {
                "parser": '''def parse_url(url):
    """Parse a URL into components."""
    pattern = r"^(?:(https?|ftp)://)?([^/:]+)(?::(\d+))?(/[^?#]*)?(?:\?([^#]*))?(?:#(.*))?$"
    match = re.match(pattern, url)
    if not match:
        return None
    scheme, host, port, path, query, fragment = match.groups()
    params = {}
    if query:
        for pair in query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = v
    return {
        "scheme": scheme or "http",
        "host": host,
        "port": int(port) if port else None,
        "path": path or "/",
        "query": query,
        "params": params,
        "fragment": fragment,
    }''',
                "validator": '''def is_valid_url(url):
    """Check if a URL is valid."""
    pattern = r"^https?://[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*(/[^\s]*)?$"
    return bool(re.match(pattern, url))


def classify_url(url):
    """Classify a URL by type."""
    if not is_valid_url(url):
        return "invalid"
    if url.endswith((".jpg", ".png", ".gif", ".svg")):
        return "image"
    if url.endswith((".mp4", ".webm", ".avi")):
        return "video"
    if url.endswith((".pdf", ".doc", ".docx")):
        return "document"
    if "/api/" in url:
        return "api"
    return "webpage"''',
            },
            "main_variants": {
                "parser": '    urls = [\n        "https://example.com:8080/path?key=value&foo=bar#section",\n        "http://localhost/api/test",\n        "https://sub.domain.com/page",\n    ]\n    for url in urls:\n        parsed = parse_url(url)\n        if parsed:\n            print(f"  {url}")\n            for k, v in parsed.items():\n                if v:\n                    print(f"    {k}: {v}")',
                "validator": '    urls = [\n        "https://example.com",\n        "http://localhost:3000/api",\n        "not-a-url",\n        "https://images.test.com/photo.jpg",\n        "ftp://invalid",\n        "https://docs.example.com/report.pdf",\n    ]\n    for url in urls:\n        valid = is_valid_url(url)\n        cls = classify_url(url)\n        print(f"  {url:45s} -> valid={valid}, type={cls}")',
            },
            "descriptions": {
                "parser": "Parse URLs into components.",
                "validator": "Validate and classify URLs.",
            },
            "base_price": 10,
        },
    ],
}


# Complexity levels for price calculation
COMPLEXITY_MULTIPLIERS = {
    "simple": 0.7,
    "medium": 1.0,
    "complex": 1.5,
}
