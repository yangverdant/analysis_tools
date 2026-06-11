"""因素注册表"""

from .standing import StandingFactor
from .form import FormFactor
from .home_away import HomeAwayFactor
from .home_away_deep import HomeAwayDeepFactor
from .euro_odds import EuroOddsFactor
from .asian_handicap import AsianHandicapFactor
from .over_under import OverUnderFactor
from .odds_movement import OddsMovementFactor
from .prediction import PredictionFactor
from .expected_goals import ExpectedGoalsFactor
from .poisson import PoissonFactor
from .h2h import H2HFactor
from .injury import InjuryFactor
from .weather import WeatherFactor
from .motivation import MotivationFactor
from .schedule_difficulty import ScheduleDifficultyFactor
from .giant_killer import GiantKillerFactor
from .rotation import RotationFactor
from .lineup import LineupFactor
from .rivalry import RivalryFactor
from .rest_days import RestDaysFactor
from .possession_counter import PossessionCounterFactor
from .elo_rating import EloRatingFactor

ALL_FACTORS = [
    StandingFactor, FormFactor, HomeAwayFactor, HomeAwayDeepFactor,
    EuroOddsFactor, AsianHandicapFactor, OverUnderFactor, OddsMovementFactor,
    PredictionFactor, ExpectedGoalsFactor, PoissonFactor, H2HFactor,
    InjuryFactor, WeatherFactor, MotivationFactor, ScheduleDifficultyFactor,
    GiantKillerFactor, RotationFactor, LineupFactor, RivalryFactor,
    RestDaysFactor, PossessionCounterFactor, EloRatingFactor,
]

FACTOR_MAP = {f.factor: f for f in ALL_FACTORS}