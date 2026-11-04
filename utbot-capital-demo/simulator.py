"""Offline execution-state simulator. NO broker calls or real order placement."""
from dataclasses import dataclass, field

@dataclass
class Simulator:
    positions: dict = field(default_factory=dict)
    realised_gbp: float = 0.0
    unrealised_gbp: dict = field(default_factory=dict)
    halted: bool = False
    limit_gbp: float = -100.0

    @property
    def net_gbp(self):
        return self.realised_gbp + sum(self.unrealised_gbp.values())

    def mark(self, market, pnl_gbp):
        self.unrealised_gbp[market] = pnl_gbp
        if self.net_gbp <= self.limit_gbp:
            self.halted = True
            # Simulate immediate close; real-world fills can slip.
            self.realised_gbp += sum(self.unrealised_gbp.values())
            self.unrealised_gbp.clear()
            self.positions.clear()
        return {'halted': self.halted, 'net_gbp': self.net_gbp}

    def signal(self, market, direction):
        if self.halted:
            return 'HALTED'
        if market not in ('GOLD', 'OIL') or direction not in ('BUY', 'SELL'):
            return 'INVALID'
        if self.positions.get(market) == direction:
            return 'UNCHANGED'
        # Simulated close before simulated new entry.
        self.realised_gbp += self.unrealised_gbp.pop(market, 0.0)
        if self.net_gbp <= self.limit_gbp:
            self.halted = True
            self.positions.clear()
            return 'HALTED'
        self.positions[market] = direction
        return 'SIMULATED_' + direction
