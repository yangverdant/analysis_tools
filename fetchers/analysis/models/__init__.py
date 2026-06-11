"""概率模型注册表"""

from .basic_linear import BasicLinearModel
from .enhanced_linear import EnhancedLinearModel
from .chain import ChainModel

ALL_MODELS = [BasicLinearModel, EnhancedLinearModel, ChainModel]
MODEL_MAP = {m().model_name: m for m in ALL_MODELS}