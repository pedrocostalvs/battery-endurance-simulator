"""Velocity profiles for preliminary endurance calculations."""

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class VelocityProfile:
    time_s: np.ndarray
    velocity_m_s: np.ndarray
    name: str
    source: str
    assumptions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        time = np.asarray(self.time_s, dtype=float)
        velocity = np.asarray(self.velocity_m_s, dtype=float)
        if time.ndim != 1 or velocity.ndim != 1 or len(time) != len(velocity):
            raise ValueError("time and velocity must be one-dimensional and equal-sized")
        if len(time) < 2:
            raise ValueError("a velocity profile needs at least two samples")
        if not np.all(np.isfinite(time)) or not np.all(np.isfinite(velocity)):
            raise ValueError("profile values must be finite")
        if not np.all(np.diff(time) > 0.0):
            raise ValueError("time must be strictly increasing")
        if np.any(velocity < 0.0):
            raise ValueError("velocity must be non-negative")
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "velocity_m_s", velocity)

    @property
    def distance_m(self) -> float:
        return float(np.sum(
            0.5 * (self.velocity_m_s[:-1] + self.velocity_m_s[1:])
            * np.diff(self.time_s)
        ))

    @property
    def duration_s(self) -> float:
        return float(self.time_s[-1] - self.time_s[0])


def _sample_piecewise_linear(
    nodes: Sequence[tuple[float, float]], sample_dt_s: float
) -> tuple[np.ndarray, np.ndarray]:
    if not np.isfinite(sample_dt_s) or sample_dt_s <= 0.0:
        raise ValueError("sample_dt_s must be finite and positive")
    node_t = np.asarray([item[0] for item in nodes], dtype=float)
    node_v = np.asarray([item[1] for item in nodes], dtype=float)
    if len(nodes) < 2 or not np.all(np.diff(node_t) > 0.0):
        raise ValueError("profile nodes must have strictly increasing time")
    if np.any(node_v < 0.0):
        raise ValueError("node velocities must be non-negative")

    times = [float(node_t[0])]
    for start, end in zip(node_t[:-1], node_t[1:]):
        count = max(1, int(np.ceil((end - start) / sample_dt_s)))
        times.extend(np.linspace(start, end, count + 1)[1:].tolist())
    time = np.asarray(times)
    return time, np.interp(time, node_t, node_v)


def build_hypothetical_endurance_cycle(sample_dt_s: float = 0.1) -> VelocityProfile:
    """Return a configurable *hypothetical*, non-Sprint endurance cycle.

    The nodes deliberately include acceleration, cruising, curve-speed
    reductions and a final braking phase. They are assumptions for an initial
    engineering scenario, not measured track telemetry.
    """
    nodes = (
        (0.0, 0.0),
        (6.0, 20.0),       # acceleration
        (14.0, 20.0),      # constant-speed straight
        (18.0, 10.0),      # braking/reduction for a slow curve
        (24.0, 10.0),      # slow curve
        (29.0, 22.0),      # acceleration out of the curve
        (37.0, 22.0),      # faster straight
        (41.0, 12.0),      # braking/reduction for another curve
        (47.0, 12.0),      # medium-speed curve
        (52.0, 20.0),      # acceleration
        (60.0, 20.0),      # constant-speed straight
        (65.0, 0.0),       # final braking, with no regeneration
    )
    time, velocity = _sample_piecewise_linear(nodes, sample_dt_s)
    return VelocityProfile(
        time_s=time,
        velocity_m_s=velocity,
        name="Ciclo hipotético de Endurance",
        source="Cenário sintético; não deriva do Sprint de 75 m",
        assumptions=(
            "Perfil linear por trechos com velocidades entre 0 e 22 m/s.",
            "O ciclo contém aceleração, retas, curvas lentas e frenagem.",
            "A frenagem não recupera energia.",
            "O ciclo é repetido como volta representativa apenas neste cenário hipotético.",
        ),
    )


def repeat_to_exact_distance(
    cycle: VelocityProfile, target_distance_m: float
) -> VelocityProfile:
    """Repeat a declared representative cycle and stop exactly at the target.

    The final interval is shortened analytically under its linear-velocity
    definition, avoiding distance extrapolation.
    """
    if not np.isfinite(target_distance_m) or target_distance_m <= 0.0:
        raise ValueError("target_distance_m must be finite and positive")
    if cycle.distance_m <= 0.0:
        raise ValueError("cycle distance must be positive")
    if not np.isclose(cycle.velocity_m_s[0], cycle.velocity_m_s[-1]):
        raise ValueError("a repeated cycle must end at its starting velocity")

    out_t = [0.0]
    out_v = [float(cycle.velocity_m_s[0])]
    distance = 0.0
    elapsed = 0.0
    index = 0
    intervals = len(cycle.time_s) - 1
    tolerance = max(1e-9, 1e-12 * target_distance_m)

    while distance < target_distance_m - tolerance:
        i = index % intervals
        dt = float(cycle.time_s[i + 1] - cycle.time_s[i])
        v0 = float(cycle.velocity_m_s[i])
        v1 = float(cycle.velocity_m_s[i + 1])
        segment_distance = 0.5 * (v0 + v1) * dt
        remaining = target_distance_m - distance

        if segment_distance <= remaining + tolerance:
            elapsed += dt
            distance += segment_distance
            out_t.append(elapsed)
            out_v.append(v1)
            index += 1
            continue

        acceleration = (v1 - v0) / dt
        if abs(acceleration) < 1e-14:
            partial_dt = remaining / v0
        else:
            discriminant = max(v0 * v0 + 2.0 * acceleration * remaining, 0.0)
            roots = (
                (-v0 + np.sqrt(discriminant)) / acceleration,
                (-v0 - np.sqrt(discriminant)) / acceleration,
            )
            valid = [root for root in roots if -tolerance <= root <= dt + tolerance]
            if not valid:
                raise ArithmeticError("could not locate target inside final interval")
            partial_dt = min(valid, key=lambda value: abs(value))
        partial_dt = float(np.clip(partial_dt, 0.0, dt))
        elapsed += partial_dt
        out_t.append(elapsed)
        out_v.append(v0 + acceleration * partial_dt)
        distance = target_distance_m

    profile = VelocityProfile(
        time_s=np.asarray(out_t),
        velocity_m_s=np.asarray(out_v),
        name=f"{cycle.name} — distância-alvo",
        source=cycle.source,
        assumptions=cycle.assumptions,
    )
    if not np.isclose(profile.distance_m, target_distance_m, atol=tolerance, rtol=0.0):
        raise ArithmeticError("final profile does not match target distance")
    return profile
