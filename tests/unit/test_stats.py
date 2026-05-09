"""Tests for inter-rater agreement statistics."""

from __future__ import annotations

import math

import pytest

from evalkit.judges.stats import (
    cohens_kappa,
    confusion_matrix,
    fleiss_kappa,
    krippendorff_alpha,
)


class TestCohensKappa:
    def test_perfect_agreement(self) -> None:
        a = [1, 2, 3, 4, 5, 1, 2, 3, 4, 5]
        assert cohens_kappa(a, a) == pytest.approx(1.0)

    def test_total_disagreement_two_categories(self) -> None:
        a = [1] * 5 + [2] * 5
        b = [2] * 5 + [1] * 5
        # Observed agreement = 0; expected = 0.5; kappa = -1
        assert cohens_kappa(a, b) == pytest.approx(-1.0)

    def test_chance_level(self) -> None:
        # Same marginals, no correlation between raters → kappa ≈ 0
        a = [1, 2, 1, 2, 1, 2, 1, 2]
        b = [2, 1, 2, 1, 2, 1, 2, 1]
        kappa = cohens_kappa(a, b)
        assert kappa == pytest.approx(-1.0)  # systematic disagreement → -1

    def test_single_category_returns_one(self) -> None:
        # If both raters use only one category, treat as full agreement.
        assert cohens_kappa([1, 1, 1], [1, 1, 1]) == 1.0

    def test_unequal_lengths_raises(self) -> None:
        with pytest.raises(ValueError, match="length"):
            cohens_kappa([1, 2], [1])

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            cohens_kappa([], [])


class TestFleissKappa:
    def test_perfect_agreement(self) -> None:
        ratings = [[1, 1, 1], [2, 2, 2], [3, 3, 3]]
        assert fleiss_kappa(ratings) == pytest.approx(1.0)

    def test_random_ratings_low_kappa(self) -> None:
        ratings = [
            [1, 2, 3],
            [3, 1, 2],
            [2, 3, 1],
            [1, 3, 2],
            [2, 1, 3],
        ]
        kappa = fleiss_kappa(ratings)
        assert -1.0 <= kappa < 0.2

    def test_too_few_raters_raises(self) -> None:
        with pytest.raises(ValueError, match="raters"):
            fleiss_kappa([[1]])

    def test_uneven_raters_raises(self) -> None:
        with pytest.raises(ValueError, match="same number"):
            fleiss_kappa([[1, 2], [1]])

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            fleiss_kappa([])


class TestKrippendorffAlpha:
    def test_nominal_perfect_agreement(self) -> None:
        ratings = [[1, 1], [2, 2], [3, 3]]
        assert krippendorff_alpha(ratings, metric="nominal") == pytest.approx(1.0)

    def test_handles_missing_values(self) -> None:
        ratings: list[list[int | None]] = [
            [1, 1, None],
            [2, 2, 2],
            [None, 3, 3],
        ]
        alpha = krippendorff_alpha(ratings, metric="nominal")
        assert math.isclose(alpha, 1.0, abs_tol=1e-9)

    def test_interval_metric_requires_numerics(self) -> None:
        with pytest.raises(ValueError, match="numeric"):
            krippendorff_alpha([["a", "b"], ["a", "b"]], metric="interval")

    def test_unsupported_metric_raises(self) -> None:
        with pytest.raises(ValueError, match="unsupported"):
            krippendorff_alpha([[1, 1]], metric="weird")  # type: ignore[arg-type]

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            krippendorff_alpha([])

    def test_no_pair_raises(self) -> None:
        with pytest.raises(ValueError, match="≥2"):
            krippendorff_alpha([[1, None], [2, None]])

    def test_interval_metric_perfect(self) -> None:
        alpha = krippendorff_alpha([[1, 1], [2, 2], [3, 3]], metric="interval")
        assert alpha == pytest.approx(1.0)


class TestConfusionMatrix:
    def test_basic(self) -> None:
        cm = confusion_matrix([1, 2, 1], [1, 2, 2])
        assert cm[(1, 1)] == 1
        assert cm[(2, 2)] == 1
        assert cm[(1, 2)] == 1

    def test_unequal_raises(self) -> None:
        with pytest.raises(ValueError, match="lengths differ"):
            confusion_matrix([1], [1, 2])
