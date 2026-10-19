"""Animation / animation-controller JSON builders (Bedrock RP formats 1.8.0 / 1.10.0)."""
from __future__ import annotations


def keyframes(*frames: tuple[float, list]) -> dict:
    return {f"{t:.2f}".rstrip("0").rstrip(".") if t else "0.0": v for t, v in frames}


class AnimSet:
    """Collects animations for one entity: AnimSet('hollow_king').add('idle', ...)."""

    def __init__(self, entity: str):
        self.entity = entity
        self.anims: dict[str, dict] = {}

    def full(self, short: str) -> str:
        return f"animation.apocalypse.{self.entity}.{short}"

    def add(self, short: str, bones: dict, loop: bool | str = True, length: float | None = None,
            override: bool = False, blend_weight: str | None = None) -> str:
        a: dict = {"loop": loop}
        if length is not None:
            a["animation_length"] = length
        if override:
            a["override_previous_animation"] = True
        if blend_weight:
            a["blend_weight"] = blend_weight
        a["bones"] = bones
        self.anims[self.full(short)] = a
        return self.full(short)

    def to_json(self) -> dict:
        return {"format_version": "1.8.0", "animations": self.anims}


class ControllerSet:
    def __init__(self, entity: str):
        self.entity = entity
        self.controllers: dict[str, dict] = {}

    def full(self, short: str) -> str:
        return f"controller.animation.apocalypse.{self.entity}.{short}"

    def property_states(self, short: str, prop: str, states: dict[int, dict], blend: float = 0.15) -> str:
        """One state per integer property value; state 0 is 'default'.

        states: {value: {"name": str, "animations": [...], "particles": [...], "sounds": [...]}}
        """
        names = {v: s["name"] for v, s in states.items()}
        st: dict = {}
        default_trans = [{names[v]: f"query.property('{prop}') == {v}"} for v in states if v != 0]
        st["default"] = {"transitions": default_trans}
        if 0 in states and states[0].get("animations"):
            st["default"]["animations"] = states[0]["animations"]
        for v, s in states.items():
            if v == 0:
                continue
            body: dict = {}
            if s.get("animations"):
                body["animations"] = s["animations"]
            if s.get("particles"):
                body["particle_effects"] = s["particles"]
            if s.get("sounds"):
                body["sound_effects"] = s["sounds"]
            body["transitions"] = [{"default": f"query.property('{prop}') != {v}"}]
            body["blend_transition"] = blend
            st[s["name"]] = body
        self.controllers[self.full(short)] = {"initial_state": "default", "states": st}
        return self.full(short)

    def always(self, short: str, animations: list | None = None, particles: list | None = None) -> str:
        body: dict = {}
        if animations:
            body["animations"] = animations
        if particles:
            body["particle_effects"] = particles
        self.controllers[self.full(short)] = {"initial_state": "default", "states": {"default": body}}
        return self.full(short)

    def to_json(self) -> dict:
        return {"format_version": "1.10.0", "animation_controllers": self.controllers}


# ------------------------------------------------------------------------------------------------
# Molang building blocks
# ------------------------------------------------------------------------------------------------
WALK = "query.modified_distance_moved"
SPEED = "query.modified_move_speed"


def swing(amp: float, phase: float = 0.0, rate: float = 38.17) -> str:
    """Leg/arm swing driven by distance moved (vanilla-style gait)."""
    p = f" + {phase}" if phase else ""
    return f"math.cos({WALK} * {rate}{p}) * {amp} * {SPEED}"


def breathe(amp: float, period: float = 3.0, phase: float = 0.0) -> str:
    rate = 360.0 / period
    p = f" + {phase}" if phase else ""
    return f"math.sin(query.life_time * {rate:.2f}{p}) * {amp}"


def bob(amp: float, period: float = 2.0, phase: float = 0.0) -> str:
    return breathe(amp, period, phase)
