import numpy as np
import pytest

from dehps.optimization.near_residual import orthogonal_residual_blend, random_top_n_overlap_baseline


def test_residual_blend_removes_static_projection() -> None:
    static = np.linspace(-3.0, 4.0, 1000)
    nonlinear_signal = np.sin(np.linspace(0.0, 20.0, 1000))
    dynamic = static + 0.8 * static + nonlinear_signal

    result = orthogonal_residual_blend(static, dynamic, residual_strength=0.25)

    assert abs(float(np.corrcoef(result.static_z, result.residual_z)[0, 1])) < 1e-12
    assert result.metadata["static_delta_correlation"] > 0.9
    assert result.metadata["degenerate_residual"] is False
    assert np.allclose(result.scores, result.static_z + 0.25 * result.residual_z)


def test_residual_blend_falls_back_to_static_when_delta_is_constant() -> None:
    static = np.array([1.0, 2.0, 3.0])
    result = orthogonal_residual_blend(static, static + 5.0, residual_strength=0.5)
    assert np.allclose(result.scores, result.static_z)
    assert result.metadata["degenerate_residual"] is True


@pytest.mark.parametrize("strength", [-1.0, float("nan")])
def test_residual_blend_rejects_invalid_strength(strength: float) -> None:
    with pytest.raises(ValueError):
        orthogonal_residual_blend(np.array([1.0]), np.array([1.0]), residual_strength=strength)


def test_random_top100_red4_baseline_is_not_small() -> None:
    probability = random_top_n_overlap_baseline(top_n=100, minimum_overlap=4)
    assert 0.37 < probability < 0.39
