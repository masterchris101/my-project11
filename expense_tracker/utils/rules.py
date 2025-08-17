import json
import os
import re
from typing import Dict, List, Optional, Tuple

from unidecode import unidecode


DEFAULT_RULES: Dict[str, List[str]] = {
    "Groceries": [
        r"\btrader\s*joe'?s?\b",
        r"\bsafeway\b",
        r"\bwhole\s*foods\b",
        r"\bcostco\b",
        r"\bheb\b",
        r"\bwalmart\b",
        r"\btarget\b",
        r"\binstacart\b",
    ],
    "Restaurants": [
        r"\bubereats\b",
        r"\bdoordash\b",
        r"\bgrubhub\b",
        r"\bstarbucks\b",
        r"\bmcdonald'?s?\b",
        r"\bchipotle\b",
        r"\btaco\s*bell\b",
        r"\bsubway\b",
        r"\bpizza\b",
        r"\bkfc\b",
        r"\bpanda\s*express\b",
    ],
    "Transport": [
        r"\buber\b",
        r"\blyft\b",
        r"\bchevron\b",
        r"\bshell\b",
        r"\bexxon\b",
        r"\bbp\b",
        r"\btesla\b",
        r"\bvalero\b",
        r"\bstation\s*gas\b",
        r"\bgas\b",
        r"\bmetro\b",
        r"\bsubway\s*station\b",
    ],
    "Housing": [
        r"\brent\b",
        r"\bmortgage\b",
        r"\blandlord\b",
        r"\bapartment\b",
        r"\bproperty\s*management\b",
        r"\bhoa\b",
    ],
    "Utilities": [
        r"\belectric\b",
        r"\bwater\b",
        r"\bgas\b",
        r"\binternet\b",
        r"\bcomcast\b",
        r"\bat\&t\b",
        r"\bverizon\b",
        r"\bt-mobile\b",
        r"\bspectrum\b",
    ],
    "Entertainment": [
        r"\bnetflix\b",
        r"\bspotify\b",
        r"\bhulu\b",
        r"\bdisney\+?\b",
        r"\bprime\s*video\b",
        r"\bxbox\b",
        r"\bplaystation\b",
        r"\bsteam\b",
    ],
    "Shopping": [
        r"\bamzn|amazon\b",
        r"\bebay\b",
        r"\betsy\b",
        r"\bbest\s*buy\b",
        r"\bapple\s*store\b",
    ],
    "Health": [
        r"\bcvs\b",
        r"\bwalgreens\b",
        r"\bpharmacy\b",
        r"\bdoctor\b",
        r"\bdentist\b",
        r"\bclinic\b",
        r"\boptical\b",
    ],
    "Travel": [
        r"\bairbnb\b",
        r"\bbooking\.com\b",
        r"\bexpedia\b",
        r"\bmarriott\b",
        r"\bhilton\b",
        r"\bdelta\b",
        r"\bamerican\s*airlines\b",
        r"\bsouthwest\b",
        r"\bunited\b",
    ],
    "Income": [
        r"\bpayroll\b",
        r"\bsalary\b",
        r"\bpaycheck\b",
        r"\bdirect\s*deposit\b",
        r"\bvenmo\s*cashout\b",
        r"\bcash\s*app\s*cashout\b",
        r"\bzelle\s*in\b",
        r"\binterest\s*payment\b",
    ],
    "Fees": [
        r"\boverdraft\b",
        r"\bmaintenance\s*fee\b",
        r"\bservice\s*charge\b",
        r"\batm\s*fee\b",
        r"\bwire\s*fee\b",
    ],
}


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    text_ascii = unidecode(str(text))
    text_ascii = text_ascii.lower().strip()
    text_ascii = re.sub(r"\s+", " ", text_ascii)
    return text_ascii


class RuleEngine:
    def __init__(self, rules_path: str = None) -> None:
        self.rules_path = rules_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "rules.json"
        )
        self.rules: Dict[str, List[str]] = {}
        self.compiled_rules: List[Tuple[re.Pattern, str]] = []
        self.load_rules()

    def load_rules(self) -> None:
        rules: Dict[str, List[str]] = {}
        rules.update(DEFAULT_RULES)
        if os.path.exists(self.rules_path):
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    file_rules = json.load(f)
                    if isinstance(file_rules, dict):
                        rules.update(file_rules)
            except Exception:
                # Ignore malformed file and keep defaults
                pass
        self.rules = rules
        self._compile()

    def save_rules(self) -> None:
        data_dir = os.path.dirname(self.rules_path)
        os.makedirs(data_dir, exist_ok=True)
        # Only save non-default custom rules to file to keep it small
        custom_rules: Dict[str, List[str]] = {}
        for category, patterns in self.rules.items():
            default_patterns = set(DEFAULT_RULES.get(category, []))
            extra = [p for p in patterns if p not in default_patterns]
            if extra:
                custom_rules[category] = extra
        with open(self.rules_path, "w", encoding="utf-8") as f:
            json.dump(custom_rules, f, indent=2, ensure_ascii=False)

    def _compile(self) -> None:
        compiled: List[Tuple[re.Pattern, str]] = []
        for category, patterns in self.rules.items():
            for pattern in patterns:
                try:
                    compiled.append((re.compile(pattern, flags=re.IGNORECASE), category))
                except re.error:
                    # Skip invalid regex pattern
                    continue
        # Sort by pattern length descending for more specific matches first
        compiled.sort(key=lambda x: len(x[0].pattern), reverse=True)
        self.compiled_rules = compiled

    def add_rule(self, category: str, pattern: str) -> None:
        category = category.strip()
        pattern = pattern.strip()
        if not category or not pattern:
            return
        if category not in self.rules:
            self.rules[category] = []
        if pattern not in self.rules[category]:
            self.rules[category].append(pattern)
        self._compile()
        self.save_rules()

    def categorize(self, description: str) -> Optional[str]:
        text = normalize_text(description)
        if not text:
            return None
        for pattern, category in self.compiled_rules:
            if pattern.search(text):
                return category
        return None