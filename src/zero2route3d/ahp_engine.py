"""Analytic Hierarchy Process (AHP) multi-criteria decision engine.

Provides pairwise comparison matrix construction, principal eigenvector weight
calculation, and Saaty consistency ratio (CR < 0.10) validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

# Saaty Random Consistency Index (RI) table for matrix sizes 1..10
RANDOM_INDEX: Dict[int, float] = {
    1: 0.00,
    2: 0.00,
    3: 0.58,
    4: 0.90,
    5: 1.12,
    6: 1.24,
    7: 1.32,
    8: 1.41,
    9: 1.45,
    10: 1.49,
}


@dataclass
class AHPResult:
    """Output of AHP analysis with weights, consistency metrics, and status."""

    criteria: List[str]
    weights: Dict[str, float]
    lambda_max: float
    consistency_index: float
    consistency_ratio: float
    is_consistent: bool
    status_message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "criteria": self.criteria,
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "lambda_max": round(self.lambda_max, 4),
            "consistency_index": round(self.consistency_index, 4),
            "consistency_ratio": round(self.consistency_ratio, 4),
            "is_consistent": self.is_consistent,
            "status_message": self.status_message,
        }


class AHPEngine:
    """Solves AHP pairwise comparison matrices for multi-criteria routing weights."""

    def __init__(self, criteria: Sequence[str]) -> None:
        self.criteria = list(criteria)
        self.n = len(self.criteria)
        self.matrix: List[List[float]] = [[1.0] * self.n for _ in range(self.n)]

    def set_pairwise_comparison(self, criterion_a: str, criterion_b: str, value: float) -> None:
        """Set pairwise importance of criterion A relative to B (1/9 to 9 scale)."""
        if criterion_a not in self.criteria or criterion_b not in self.criteria:
            return
        i = self.criteria.index(criterion_a)
        j = self.criteria.index(criterion_b)
        val = max(1.0 / 9.0, min(9.0, float(value)))
        self.matrix[i][j] = val
        self.matrix[j][i] = 1.0 / val

    def calculate(self) -> AHPResult:
        """Compute principal eigenvector weights and consistency ratio."""
        if self.n == 0:
            return AHPResult([], {}, 0.0, 0.0, 0.0, True, "Empty criteria.")
        if self.n == 1:
            return AHPResult(
                self.criteria, {self.criteria[0]: 1.0}, 1.0, 0.0, 0.0, True, "Single criterion."
            )

        # 1. Normalize columns
        col_sums = [sum(self.matrix[row][col] for row in range(self.n)) for col in range(self.n)]
        norm_matrix = [
            [self.matrix[row][col] / max(1e-9, col_sums[col]) for col in range(self.n)]
            for row in range(self.n)
        ]

        # 2. Row averages (eigenvector weights)
        weights_list = [sum(norm_matrix[row]) / self.n for row in range(self.n)]
        weights = {self.criteria[i]: weights_list[i] for i in range(self.n)}

        # 3. Maximum Eigenvalue (lambda_max)
        weighted_sum_vector = [
            sum(self.matrix[row][col] * weights_list[col] for col in range(self.n))
            for row in range(self.n)
        ]
        ratios = [weighted_sum_vector[i] / max(1e-9, weights_list[i]) for i in range(self.n)]
        lambda_max = sum(ratios) / self.n

        # 4. Consistency Index (CI) and Consistency Ratio (CR)
        ci = (lambda_max - self.n) / max(1, self.n - 1)
        ri = RANDOM_INDEX.get(self.n, 1.49)
        cr = (ci / ri) if ri > 0 else 0.0

        is_consistent = cr <= 0.10 or self.n <= 2
        msg = (
            f"Consistent (CR = {cr:.3f} <= 0.10)"
            if is_consistent
            else f"Inconsistent (CR = {cr:.3f} > 0.10); consider revising pairwise judgements."
        )

        return AHPResult(
            criteria=self.criteria,
            weights=weights,
            lambda_max=lambda_max,
            consistency_index=ci,
            consistency_ratio=cr,
            is_consistent=is_consistent,
            status_message=msg,
        )
