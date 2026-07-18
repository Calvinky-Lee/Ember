"""Builds data/workloads/default.json (spec 05 / task P3-M1).

Provenance, per category:
- trivial (50): hand-written here — real product-shaped queries (formatting,
  extraction, one-fact QA). Deterministic oracles.
- math (40): random sample (seed 42) from the official GSM8K test split
  (github.com/openai/grade-school-math). Ground-truth answers parsed from the
  dataset's '#### N' terminator. numeric_exact oracle.
- reasoning (40): hand-written here — short logic/why/inference with reference
  answers. judge oracle (scored at evaluation time, spec 09 layer 2).
- code (20): hand-written here — small functions with assert-based unit_test
  oracles (deterministic).

Run:  uv run python scripts/build_workload.py
"""
import json
import random
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "workloads" / "default.json"
GSM8K_URL = "https://raw.githubusercontent.com/openai/grade-school-math/master/grade_school_math/data/test.jsonl"
GSM8K_CACHE = Path("/tmp/gsm8k_test.jsonl")
MATH_SUFFIX = "\n\nGive the final numeric answer at the end of your response."

TRIVIAL = [
    # (prompt, oracle_type, answer) — prompts instruct a terse reply so the
    # contains/numeric oracles are robust to model verbosity.
    ("What is the capital of France? Reply with only the city name.", "string_match", "Paris"),
    ("What is the capital of Japan? Reply with only the city name.", "string_match", "Tokyo"),
    ("What is the chemical symbol for gold? Reply with only the symbol.", "string_match", "Au"),
    ("What is the largest planet in our solar system? Reply with only its name.", "string_match", "Jupiter"),
    ("Who wrote the novel 1984? Reply with only the author's surname.", "string_match", "Orwell"),
    ("What is the common name for H2O? Reply with one word.", "string_match", "water"),
    ("What is the opposite of the word 'hot'? Reply with one word.", "string_match", "cold"),
    ("What pigment makes plant leaves green? Reply with one word.", "string_match", "chlorophyll"),
    ("What is the currency of the United Kingdom? Reply with one word.", "string_match", "pound"),
    ("On which continent is Egypt? Reply with one word.", "string_match", "Africa"),
    ("What is 15% of 80? Reply with only the number.", "numeric_exact", "12"),
    ("What is 7 times 8? Reply with only the number.", "numeric_exact", "56"),
    ("What is 144 divided by 12? Reply with only the number.", "numeric_exact", "12"),
    ("What is 25 plus 17? Reply with only the number.", "numeric_exact", "42"),
    ("What is 100 minus 37? Reply with only the number.", "numeric_exact", "63"),
    ("What is the square of 9? Reply with only the number.", "numeric_exact", "81"),
    ("What is half of 250? Reply with only the number.", "numeric_exact", "125"),
    ("What is 2 to the power of 10? Reply with only the number.", "numeric_exact", "1024"),
    ("How many minutes are in a day? Reply with only the number.", "numeric_exact", "1440"),
    ("What is 15 times 15? Reply with only the number.", "numeric_exact", "225"),
    ("Convert 'hello world' to uppercase. Reply with only the result.", "string_match", "HELLO WORLD"),
    ("Convert 'PYTHON' to lowercase. Reply with only the result.", "string_match", "python"),
    ("Reverse the string 'stressed'. Reply with only the result.", "string_match", "desserts"),
    ("What acronym is formed by the first letters of 'as soon as possible'? Reply with only the acronym.", "string_match", "ASAP"),
    ("Join the items a, b, c with hyphens. Reply with only the result.", "string_match", "a-b-c"),
    ("Extract the year from this sentence: 'The company was founded in 1998 in Toronto.' Reply with only the year.", "numeric_exact", "1998"),
    ("Extract the email address from: 'Contact us at support@ember.dev for help.' Reply with only the address.", "string_match", "support@ember.dev"),
    ("Remove all vowels from the word 'keyboard'. Reply with only the result.", "string_match", "kybrd"),
    ("Replace the spaces in 'new york city' with underscores. Reply with only the result.", "string_match", "new_york_city"),
    ("What is the third word of 'the quick brown fox'? Reply with only that word.", "string_match", "brown"),
    ("Sort the letters of 'cab' alphabetically. Reply with only the result.", "string_match", "abc"),
    ("Repeat the string 'ab' three times with no separator. Reply with only the result.", "string_match", "ababab"),
    ("How many letters are in the word 'banana'? Reply with only the number.", "numeric_exact", "6"),
    ("What are the initials of John Ronald Reuel Tolkien? Reply with only the initials, no periods.", "string_match", "JRRT"),
    ("Convert 'UserProfileSettings' to snake_case. Reply with only the result.", "string_match", "user_profile_settings"),
    ("How many minutes are in 2.5 hours? Reply with only the number.", "numeric_exact", "150"),
    ("How many days does February have in a leap year? Reply with only the number.", "numeric_exact", "29"),
    ("How many centimeters are in 2 meters? Reply with only the number.", "numeric_exact", "200"),
    ("What is 0 degrees Celsius in Fahrenheit? Reply with only the number.", "numeric_exact", "32"),
    ("How many items are in a dozen? Reply with only the number.", "numeric_exact", "12"),
    ("How many days are in a week? Reply with only the number.", "numeric_exact", "7"),
    ("What is 9 in Roman numerals? Reply with only the numeral.", "string_match", "IX"),
    ("What is 5 in binary? Reply with only the binary digits.", "string_match", "101"),
    ("How many seconds are in an hour? Reply with only the number.", "numeric_exact", "3600"),
    ("How many sides does a hexagon have? Reply with only the number.", "numeric_exact", "6"),
    ("What does DNS stand for in networking? Reply with only the expansion.", "string_match", "domain name system"),
    ("What is the default port for HTTP? Reply with only the number.", "numeric_exact", "80"),
    ("At what temperature in Celsius does water boil at sea level? Reply with only the number.", "numeric_exact", "100"),
    ("How many continents are there? Reply with only the number.", "numeric_exact", "7"),
    ("What is the first element of the periodic table? Reply with only its name.", "string_match", "hydrogen"),
]

REASONING = [
    ("Why does ice float on water?", "Ice is less dense than liquid water because water expands when it freezes, so it floats."),
    ("Alice is taller than Bob. Bob is taller than Carol. Who is the shortest?", "Carol."),
    ("If all bloops are razzies and all razzies are lazzies, are all bloops lazzies? Explain briefly.", "Yes — the relation is transitive, so all bloops are lazzies."),
    ("A bat and a ball cost $1.10 together. The bat costs $1.00 more than the ball. How much does the ball cost? Explain briefly.", "The ball costs 5 cents; then the bat is $1.05 and the difference is exactly $1.00."),
    ("Why do we see lightning before we hear thunder?", "Light travels much faster than sound, so the flash arrives before the sound does."),
    ("Which is heavier: a kilogram of feathers or a kilogram of steel? Explain briefly.", "Neither — they weigh the same, one kilogram each."),
    ("A train leaves at 3:00 pm traveling at a constant 60 km/h. How far has it gone by 5:30 pm? Explain briefly.", "2.5 hours at 60 km/h is 150 km."),
    ("Why does a metal spoon feel colder than a wooden spoon in the same room?", "Both are at the same temperature, but metal conducts heat away from your hand faster, so it feels colder."),
    ("Tom's mother has three children. The first is named Snap, the second is named Crackle. What is the third child's name?", "Tom."),
    ("Can a man legally marry his widow's sister? Explain briefly.", "No — if he has a widow, he is dead."),
    ("Why is the sky blue?", "Air molecules scatter shorter blue wavelengths of sunlight more than other colors (Rayleigh scattering)."),
    ("If 3 machines make 3 widgets in 3 minutes, how long would 100 machines take to make 100 widgets? Explain briefly.", "3 minutes — each machine makes one widget in 3 minutes, and they work in parallel."),
    ("Why do ships made of steel float even though steel is denser than water?", "The hull encloses air, so the ship's average density is less than water; it displaces its own weight in water."),
    ("Why do leaves change color in autumn?", "Chlorophyll breaks down in autumn, revealing yellow and orange pigments that were masked, and some trees produce red pigments."),
    ("In a race, you overtake the person in second place. What place are you in now?", "Second place — you took their position, not first."),
    ("Why does bread dough rise?", "Yeast ferments sugars and releases carbon dioxide, which forms bubbles that expand the dough."),
    ("Which month of the year has 28 days? Explain briefly.", "All twelve months have at least 28 days."),
    ("Why can't you see stars during the day?", "Sunlight scattered by the atmosphere makes the sky far brighter than the stars, washing them out; the stars are still there."),
    ("A farmer has 17 sheep. All but 9 run away. How many sheep are left?", "9 — 'all but 9' means 9 remain."),
    ("Why do wet clothes make you feel cold?", "Evaporating water absorbs heat from your skin, cooling you down."),
    ("Two coins add up to 30 cents and one of them is not a quarter. What are they? Explain briefly.", "A quarter and a nickel — only ONE of them is not a quarter (the nickel)."),
    ("Why is it easier to float in the ocean than in a swimming pool?", "Salt water is denser than fresh water, so it provides more buoyant force."),
    ("Which weighs more: one liter of liquid water or one liter of ice? Explain briefly.", "The liter of liquid water — ice is less dense, so a liter of ice contains less mass."),
    ("Why do airplanes usually take off facing into the wind?", "A headwind increases airflow over the wings, generating the lift needed at a lower ground speed."),
    ("If yesterday was Thursday, what day will it be the day after tomorrow? Explain briefly.", "Today is Friday, tomorrow Saturday, so the day after tomorrow is Sunday."),
    ("Why does a straw look bent where it enters a glass of water?", "Light refracts (changes direction) as it passes between water and air, making the submerged part appear displaced."),
    ("How many times can you subtract 5 from 25? Explain briefly.", "Once — after that you are subtracting from 20, not 25."),
    ("Why is salt spread on icy roads?", "Salt lowers the freezing point of water, so ice melts at temperatures where it would otherwise stay frozen."),
    ("A rooster lays an egg on the exact peak of a roof. Which side does the egg roll down?", "Neither — roosters don't lay eggs."),
    ("Why are manhole covers round?", "A circle can't fall through its own hole — a round cover can't be dropped in diagonally, unlike a square one."),
    ("A glass holds water with an ice cube floating in it. When the ice melts, does the water level rise, fall, or stay the same? Explain briefly.", "It stays the same — the floating ice already displaces exactly the weight of water it becomes when melted."),
    ("Why does popcorn pop?", "Moisture inside the sealed kernel turns to steam; pressure builds until the hull ruptures and the starch expands."),
    ("If 5 cats catch 5 mice in 5 minutes, how many cats are needed to catch 100 mice in 100 minutes? Explain briefly.", "5 cats — each cat catches one mouse per 5 minutes, so 5 cats catch 100 mice in 100 minutes."),
    ("Why does the Moon show phases?", "As the Moon orbits Earth, we see different fractions of its sunlit half, producing the phases."),
    ("In a single-elimination tournament with 64 players, how many matches are played to decide the champion? Explain briefly.", "63 — every match eliminates exactly one player, and 63 players must be eliminated."),
    ("Why do fizzy drinks go flat after being opened?", "Opening releases pressure, so dissolved carbon dioxide escapes from the liquid over time."),
    ("A drawer has 10 black socks and 10 white socks. Without looking, how many must you pull out to guarantee a matching pair? Explain briefly.", "3 — with only two colors, three socks must include two of the same color."),
    ("Why do people lean forward when climbing a steep hill?", "Leaning forward keeps their center of gravity over their feet, maintaining balance against the slope."),
    ("If 4 painters take 8 hours to paint a house, how long would 8 painters take, assuming they work at the same rate? Explain briefly.", "4 hours — double the painters, half the time (32 painter-hours total)."),
    ("Why does honey pour more slowly than water?", "Honey has a much higher viscosity — stronger internal friction between its molecules resists flow."),
]

CODE = [
    ("is_palindrome(s)", "returns True if the string s reads the same forwards and backwards (case-sensitive), else False",
     ["assert is_palindrome('racecar') == True", "assert is_palindrome('hello') == False", "assert is_palindrome('') == True"]),
    ("factorial(n)", "returns n! for a non-negative integer n",
     ["assert factorial(0) == 1", "assert factorial(5) == 120"]),
    ("count_vowels(s)", "returns the number of vowels (aeiou, lowercase) in the string s",
     ["assert count_vowels('banana') == 3", "assert count_vowels('xyz') == 0"]),
    ("fib(n)", "returns the n-th Fibonacci number with fib(0)=0 and fib(1)=1",
     ["assert fib(0) == 0", "assert fib(1) == 1", "assert fib(10) == 55"]),
    ("is_prime(n)", "returns True if the integer n is prime, else False",
     ["assert is_prime(7) == True", "assert is_prime(1) == False", "assert is_prime(12) == False"]),
    ("sum_evens(nums)", "returns the sum of the even numbers in the list nums",
     ["assert sum_evens([1, 2, 3, 4]) == 6", "assert sum_evens([]) == 0"]),
    ("dedupe(items)", "returns a new list with duplicates removed, preserving first-seen order",
     ["assert dedupe([1, 2, 1, 3, 2]) == [1, 2, 3]", "assert dedupe([]) == []"]),
    ("is_anagram(a, b)", "returns True if strings a and b are anagrams of each other (case-sensitive), else False",
     ["assert is_anagram('listen', 'silent') == True", "assert is_anagram('cat', 'dog') == False"]),
    ("title_case(s)", "returns s with the first letter of each space-separated word uppercased and the rest lowercased",
     ["assert title_case('hello world') == 'Hello World'", "assert title_case('PYTHON') == 'Python'"]),
    ("c_to_f(c)", "converts a temperature from Celsius to Fahrenheit",
     ["assert c_to_f(0) == 32", "assert c_to_f(100) == 212"]),
    ("gcd(a, b)", "returns the greatest common divisor of positive integers a and b",
     ["assert gcd(12, 18) == 6", "assert gcd(7, 13) == 1"]),
    ("flatten(lst)", "flattens a list of lists one level deep into a single list",
     ["assert flatten([[1, 2], [3], []]) == [1, 2, 3]", "assert flatten([]) == []"]),
    ("second_largest(nums)", "returns the second-largest distinct value in the list nums (assume it exists)",
     ["assert second_largest([1, 5, 3, 5]) == 3", "assert second_largest([2, 1]) == 1"]),
    ("clamp(x, lo, hi)", "returns x clamped to the inclusive range [lo, hi]",
     ["assert clamp(5, 0, 10) == 5", "assert clamp(-3, 0, 10) == 0", "assert clamp(99, 0, 10) == 10"]),
    ("reverse_words(s)", "returns the words of s (single-space separated) in reverse order",
     ["assert reverse_words('the quick fox') == 'fox quick the'", "assert reverse_words('one') == 'one'"]),
    ("count_char(s, c)", "returns how many times character c appears in string s",
     ["assert count_char('mississippi', 's') == 4", "assert count_char('abc', 'z') == 0"]),
    ("merge_sorted(a, b)", "merges two already-sorted lists into one sorted list",
     ["assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]", "assert merge_sorted([], [1]) == [1]"]),
    ("digits_sum(n)", "returns the sum of the decimal digits of the non-negative integer n",
     ["assert digits_sum(1234) == 10", "assert digits_sum(0) == 0"]),
    ("swap_case(s)", "returns s with uppercase letters lowercased and vice versa",
     ["assert swap_case('aBc') == 'AbC'", "assert swap_case('') == ''"]),
    ("running_max(nums)", "returns a list where element i is the max of nums[0..i]",
     ["assert running_max([3, 1, 4, 1, 5]) == [3, 3, 4, 4, 5]", "assert running_max([]) == []"]),
]


def load_gsm8k(n: int, seed: int) -> list[dict]:
    if not GSM8K_CACHE.exists():
        urllib.request.urlretrieve(GSM8K_URL, GSM8K_CACHE)
    problems = [json.loads(line) for line in GSM8K_CACHE.read_text().splitlines() if line.strip()]
    sample = random.Random(seed).sample(problems, n)
    tasks = []
    for i, p in enumerate(sample, 1):
        final = p["answer"].split("####")[-1].strip().replace(",", "")
        tasks.append({
            "id": f"gsm8k-{i:03d}", "category": "math",
            "prompt": p["question"] + MATH_SUFFIX,
            "oracle": {"type": "numeric_exact", "answer": final},
        })
    return tasks


def main() -> None:
    tasks = []
    for i, (prompt, otype, ans) in enumerate(TRIVIAL, 1):
        tasks.append({"id": f"trivial-{i:03d}", "category": "trivial", "prompt": prompt,
                      "oracle": {"type": otype, "answer": ans}})
    tasks += load_gsm8k(40, seed=42)
    for i, (prompt, ref) in enumerate(REASONING, 1):
        tasks.append({"id": f"reason-{i:03d}", "category": "reasoning", "prompt": prompt,
                      "oracle": {"type": "judge", "reference": ref}})
    for i, (sig, desc, tests) in enumerate(CODE, 1):
        tasks.append({
            "id": f"code-{i:03d}", "category": "code",
            "prompt": f"Write a Python function `{sig}` that {desc}. Return only the code, no explanation.",
            "oracle": {"type": "unit_test", "tests": tests},
        })
    out = {
        "_source": {
            "trivial": "hand-written (this repo, scripts/build_workload.py)",
            "math": f"GSM8K official test split, {GSM8K_URL}, random sample n=40 seed=42; standard numeric-answer suffix appended",
            "reasoning": "hand-written (this repo) with reference answers",
            "code": "hand-written (this repo) with assert-based unit tests",
        },
        "tasks": tasks,
    }
    OUT.write_text(json.dumps(out, indent=1))
    counts = {}
    for t in tasks:
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    print(f"wrote {OUT} — {len(tasks)} tasks: {counts}")


if __name__ == "__main__":
    main()
