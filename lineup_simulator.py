import argparse
import csv
import dataclasses
import math
import random
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

SALARY_CAP = 50000
ENTRY_FEE = 20
TOP_PRIZE = 200000
MIN_CASH = 40
CASH_PERCENTILE = 0.75
TOP_PERCENTILE = 0.99


@dataclasses.dataclass(frozen=True)
class Player:
    name: str
    team: str
    salary: int
    position: str
    projection: float
    std_dev: float
    ceiling: float
    bust: float
    boom: float
    slate: str
    ownership: float
    optimal: float
    leverage: float

    @classmethod
    def from_row(cls, row: Dict[str, str]) -> "Player":
        return cls(
            name=row["Name"],
            team=row["Team"],
            salary=int(row["Salary"]),
            position=row["Position"],
            projection=float(row["Projection"]),
            std_dev=float(row["StdDev"]),
            ceiling=float(row["Ceiling"]),
            bust=float(row["Bust"]),
            boom=float(row["Boom"]),
            slate=row["Slate"],
            ownership=float(row["Ownership"]),
            optimal=float(row["Optimal"]),
            leverage=float(row["Leverage"]),
        )


@dataclasses.dataclass
class Lineup:
    players: List[Player]

    def salary(self) -> int:
        return sum(player.salary for player in self.players)

    def projection(self) -> float:
        return sum(player.projection for player in self.players)

    def ceiling(self) -> float:
        return sum(player.ceiling for player in self.players)

    def ownership(self) -> float:
        return sum(player.ownership for player in self.players)

    def sample_score(self, rng: random.Random) -> float:
        score = 0.0
        for player in self.players:
            sampled = rng.gauss(player.projection, player.std_dev)
            sampled = max(0.0, min(player.ceiling, sampled))
            score += sampled
        return score


class LineupSimulator:
    def __init__(self, players: Sequence[Player], seed: int | None = None) -> None:
        self.players = [p for p in players if p.slate.lower() == "main" and p.salary > 0]
        self.rng = random.Random(seed)
        self.players_by_pos = defaultdict(list)
        for player in self.players:
            self.players_by_pos[player.position].append(player)
        self.flex_pool = [p for p in self.players if p.position in {"RB", "WR", "TE"}]

    def selection_weight(self, player: Player) -> float:
        leverage_bonus = 1 + player.leverage / 100
        boom_bonus = 1 + player.boom / 100
        ownership_tax = 1 + (player.ownership / 100) * 0.35
        return max(0.01, player.projection * leverage_bonus * boom_bonus / ownership_tax)

    def random_choice(self, pool: Sequence[Player]) -> Player:
        weights = [self.selection_weight(p) for p in pool]
        return self.rng.choices(pool, weights=weights, k=1)[0]

    def generate_lineup(self) -> Lineup | None:
        for _ in range(200):
            qb = self.random_choice(self.players_by_pos["QB"])
            dst = self.random_choice(self.players_by_pos["DST"])

            rbs = self._choose_unique("RB", 2, {qb, dst})
            wrs = self._choose_unique("WR", 3, {qb, dst, *rbs})
            tes = self._choose_unique("TE", 1, {qb, dst, *rbs, *wrs})
            if None in rbs or None in wrs or None in tes:
                continue

            used = {qb, dst, *rbs, *wrs, *tes}
            flex = self._choose_flex(used)
            if flex is None:
                continue

            lineup_players = [qb, dst, *rbs, *wrs, *tes, flex]
            lineup = Lineup(lineup_players)
            if lineup.salary() <= SALARY_CAP:
                return lineup
        return None

    def _choose_unique(self, position: str, count: int, used: set[Player]) -> Tuple[Player | None, ...]:
        pool = [p for p in self.players_by_pos[position] if p not in used]
        choices: List[Player | None] = []
        for _ in range(count):
            if not pool:
                return tuple([None] * count)
            pick = self.random_choice(pool)
            choices.append(pick)
            pool = [p for p in pool if p != pick]
        return tuple(choices)

    def _choose_flex(self, used: set[Player]) -> Player | None:
        pool = [p for p in self.flex_pool if p not in used]
        if not pool:
            return None
        return self.random_choice(pool)

    def generate_lineups(self, count: int) -> List[Lineup]:
        lineups: List[Lineup] = []
        attempts = 0
        while len(lineups) < count and attempts < count * 50:
            lineup = self.generate_lineup()
            attempts += 1
            if lineup is None:
                continue
            if any(self._is_duplicate(lineup, existing) for existing in lineups):
                continue
            lineups.append(lineup)
        return lineups

    def _is_duplicate(self, a: Lineup, b: Lineup) -> bool:
        names_a = sorted(p.name for p in a.players)
        names_b = sorted(p.name for p in b.players)
        return names_a == names_b

    def simulate_scores(self, lineup: Lineup, simulations: int = 400) -> List[float]:
        return [lineup.sample_score(self.rng) for _ in range(simulations)]

    def simulate_field_scores(self, field_lineups: int = 2000, simulations: int = 80) -> List[float]:
        scores: List[float] = []
        for _ in range(field_lineups):
            lineup = self.generate_lineup()
            if lineup is None:
                continue
            scores.extend(self.simulate_scores(lineup, simulations=simulations))
        return scores

    def evaluate_lineup(self, lineup: Lineup, field_scores: Sequence[float]) -> Dict[str, float]:
        lineup_scores = self.simulate_scores(lineup)
        cash_cut = percentile(field_scores, CASH_PERCENTILE)
        top_cut = percentile(field_scores, TOP_PERCENTILE)

        cash_hits = sum(1 for score in lineup_scores if score >= cash_cut)
        top_hits = sum(1 for score in lineup_scores if score >= top_cut)

        cash_prob = cash_hits / len(lineup_scores)
        top_prob = top_hits / len(lineup_scores)

        expected_return = top_prob * TOP_PRIZE + max(0.0, cash_prob - top_prob) * MIN_CASH
        roi = expected_return / ENTRY_FEE - 1

        return {
            "projection": lineup.projection(),
            "ceiling": lineup.ceiling(),
            "ownership": lineup.ownership(),
            "cash_prob": cash_prob,
            "top_prob": top_prob,
            "roi": roi,
        }


def percentile(data: Sequence[float], pct: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * pct
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    d0 = sorted_data[int(f)] * (c - k)
    d1 = sorted_data[int(c)] * (k - f)
    return d0 + d1


def summarize_exposure(lineups: Iterable[Lineup]) -> Counter:
    counts: Counter = Counter()
    for lineup in lineups:
        for player in lineup.players:
            counts[player.name] += 1
    return counts


def load_players(path: str) -> List[Player]:
    with open(path, newline="") as fp:
        reader = csv.DictReader(fp)
        return [Player.from_row(row) for row in reader]


def format_lineup(lineup: Lineup, metrics: Dict[str, float]) -> str:
    names = ", ".join(f"{p.name} ({p.position})" for p in sorted(lineup.players, key=lambda p: p.position))
    return (
        f"Salary: {lineup.salary():>5} | Proj: {metrics['projection']:.1f} | "
        f"Ceil: {metrics['ceiling']:.1f} | Cash%: {metrics['cash_prob']*100:>5.1f} | "
        f"Top1%: {metrics['top_prob']*100:>5.2f} | ROI: {metrics['roi']*100:>6.1f}%\n"
        f"Players: {names}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Monte Carlo DFS lineup simulator for GPP strategy")
    parser.add_argument("--players", default="data/players.csv", help="Path to player CSV file")
    parser.add_argument("--lineups", type=int, default=25, help="Number of candidate lineups to generate")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for reproducibility")
    args = parser.parse_args()

    players = load_players(args.players)
    simulator = LineupSimulator(players, seed=args.seed)

    field_scores = simulator.simulate_field_scores()
    lineups = simulator.generate_lineups(args.lineups)

    evaluations = []
    for lineup in lineups:
        metrics = simulator.evaluate_lineup(lineup, field_scores)
        evaluations.append((lineup, metrics))

    evaluations.sort(key=lambda pair: pair[1]["roi"], reverse=True)

    print("Top simulated lineups by ROI (top-heavy GPP focus):")
    for idx, (lineup, metrics) in enumerate(evaluations[:10], start=1):
        print(f"\n#{idx}\n{format_lineup(lineup, metrics)}")

    exposure = summarize_exposure(lineups)
    total_lineups = len(lineups)
    print("\nExposure summary (player, % of generated lineups):")
    for name, count in exposure.most_common(15):
        pct = (count / total_lineups) * 100
        print(f"- {name}: {pct:>5.1f}%")


if __name__ == "__main__":
    main()
