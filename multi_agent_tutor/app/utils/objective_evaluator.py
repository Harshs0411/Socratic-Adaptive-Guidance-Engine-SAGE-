import re
import math
from typing import List, Tuple


def normalize_text(text: str) -> str:
    """
    Normalize text for semantic/exact-answer comparison.
    """

    text = text.lower().strip()

    # Remove LaTeX delimiters.
    text = text.replace("\\(", "")
    text = text.replace("\\)", "")
    text = text.replace("$", "")

    # Normalize common mathematical wording.
    replacements = {
        "element-wise": "elementwise",
        "element wise": "elementwise",
        "corresponding": "pairwise",
        "multiply": "multiplication",
        "multiplying": "multiplication",
        "products": "product",
        "summed": "sum",
        "adding": "sum",
        "addition": "sum",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Keep words/numbers, remove punctuation.
    text = re.sub(r"[^a-z0-9\s\-\+\.\[\],]", " ", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def extract_numbers(text: str) -> List[float]:
    """
    Extract numerical values from text.
    """

    matches = re.findall(
        r"-?\d+(?:\.\d+)?",
        text,
    )

    return [float(value) for value in matches]


def parse_number(text: str) -> float:
    """
    Parse a single numerical answer.
    """

    numbers = extract_numbers(text)

    if len(numbers) != 1:
        raise ValueError(
            f"Expected one number, found: {numbers}"
        )

    return numbers[0]


def parse_sequence(text: str) -> List[float]:
    """
    Parse a numerical sequence such as:

        [3, 10, 8]

    or:

        3, 10, 8
    """

    numbers = extract_numbers(text)

    if not numbers:
        raise ValueError(
            "No numerical sequence found."
        )

    return numbers


def parse_set(text: str) -> set:
    """
    Parse an unordered set of numerical values.
    """

    numbers = extract_numbers(text)

    return set(numbers)


def evaluate_numeric(
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:

    try:
        expected = parse_number(
            expected_answer
        )

        actual = parse_number(
            student_answer
        )

    except ValueError as exc:

        return (
            False,
            f"Could not parse numerical answer: {exc}"
        )

    if math.isclose(
        expected,
        actual,
        rel_tol=1e-6,
        abs_tol=1e-6,
    ):

        return (
            True,
            "Correct numerical answer."
        )

    return (
        False,
        (
            f"Incorrect numerical answer. "
            f"Expected {expected}, got {actual}."
        ),
    )


def evaluate_sequence(
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:

    try:
        expected = parse_sequence(
            expected_answer
        )

        actual = parse_sequence(
            student_answer
        )

    except ValueError as exc:

        return (
            False,
            f"Could not parse sequence: {exc}"
        )

    if len(expected) != len(actual):

        return (
            False,
            (
                f"Incorrect sequence length. "
                f"Expected {expected}, got {actual}."
            ),
        )

    for exp, act in zip(
        expected,
        actual,
    ):

        if not math.isclose(
            exp,
            act,
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):

            return (
                False,
                (
                    f"Incorrect sequence. "
                    f"Expected {expected}, got {actual}."
                ),
            )

    return (
        True,
        "Correct sequence."
    )


def evaluate_set(
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:

    expected = parse_set(
        expected_answer
    )

    actual = parse_set(
        student_answer
    )

    if expected == actual:

        return (
            True,
            "Correct set of values."
        )

    return (
        False,
        (
            f"Incorrect set. "
            f"Expected {expected}, got {actual}."
        ),
    )


def evaluate_exact(
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:
    """
    Evaluate a short-answer concept/term.

    This is intentionally more flexible than literal
    string equality.

    For example:

        Expected:
        elementwise multiplication and summation

        Student:
        Multiply the overlapping samples element-by-
        element, then sum the products.

    should be accepted.
    """

    expected = normalize_text(
        expected_answer
    )

    actual = normalize_text(
        student_answer
    )

    if not expected or not actual:

        return (
            False,
            "No meaningful answer was provided."
        )

    # --------------------------------------------------
    # DIRECT MATCH
    # --------------------------------------------------

    if expected == actual:

        return (
            True,
            "Correct exact answer."
        )

    # --------------------------------------------------
    # SPECIAL CASE:
    # MULTIPLICATION + SUMMATION
    # --------------------------------------------------

    multiplication_terms = (
        "multiplication",
        "multiply",
        "multiplying",
        "product",
        "products",
    )

    summation_terms = (
        "sum",
        "summation",
        "addition",
        "add",
        "adding",
    )

    has_multiplication = any(
        term in actual
        for term in multiplication_terms
    )

    has_summation = any(
        term in actual
        for term in summation_terms
    )

    expected_is_multiply_sum = (
        "multiplication" in expected
        and "sum" in expected
    )

    if (
        expected_is_multiply_sum
        and has_multiplication
        and has_summation
    ):

        return (
            True,
            (
                "Correct. The answer identifies "
                "elementwise multiplication followed "
                "by summation."
            ),
        )

    # --------------------------------------------------
    # TOKEN OVERLAP
    # --------------------------------------------------

    expected_tokens = set(
        expected.split()
    )

    actual_tokens = set(
        actual.split()
    )

    if expected_tokens:

        overlap = (
            len(
                expected_tokens
                & actual_tokens
            )
            / len(expected_tokens)
        )

        if overlap >= 0.75:

            return (
                True,
                "Answer matches the expected key ideas."
            )

    return (
        False,
        (
            f"Answer does not match the expected "
            f"answer: '{expected_answer}'."
        ),
    )


def evaluate_symbolic(
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:
    """
    Basic symbolic comparison.

    This intentionally performs conservative
    normalization rather than trying to implement
    a complete symbolic mathematics engine.
    """

    expected = normalize_text(
        expected_answer
    )

    actual = normalize_text(
        student_answer
    )

    if expected == actual:

        return (
            True,
            "Correct symbolic answer."
        )

    return (
        False,
        (
            f"Incorrect symbolic answer. "
            f"Expected '{expected_answer}', "
            f"got '{student_answer}'."
        ),
    )


def evaluate_objective_answer(
    evaluator_type: str,
    expected_answer: str,
    student_answer: str,
) -> Tuple[bool, str]:
    """
    Route an objective answer to the appropriate
    deterministic evaluator.
    """

    if evaluator_type == "numeric":

        return evaluate_numeric(
            expected_answer,
            student_answer,
        )

    if evaluator_type == "sequence":

        return evaluate_sequence(
            expected_answer,
            student_answer,
        )

    if evaluator_type == "set":

        return evaluate_set(
            expected_answer,
            student_answer,
        )

    if evaluator_type == "symbolic":

        return evaluate_symbolic(
            expected_answer,
            student_answer,
        )

    if evaluator_type == "exact":

        return evaluate_exact(
            expected_answer,
            student_answer,
        )

    raise ValueError(
        f"Unsupported evaluator type: "
        f"{evaluator_type}"
    )