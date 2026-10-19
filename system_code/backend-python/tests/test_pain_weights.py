"""疼痛权重必须可从 FACS/PSPI 推导，而非启发式拍脑袋。

修正的实质错误：旧权重把 Fear 排第一（0.9），但 Fear 含 AU1+2（眉**上抬**），
而疼痛核心 AU4 是眉**下压** —— 方向冲突，Fear 不是好的疼痛代理。
真正最贴合的是 Disgust（AU9 鼻皱，特异性最高）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'third_party' / 'ultralytics'))

from expression_recognition.system import PAIN_AUS, PAIN_WEIGHTS, _EMOTION_PAIN_AUS


def test_pain_aus_match_pspi_components():
    assert set(PAIN_AUS) == {'AU4', 'AU6_7', 'AU9', 'AU10'}, 'PSPI 四成分'


def test_disgust_outranks_fear():
    """AU9（鼻皱）比 AU4+AU6_7 更特异 → Disgust 应高于 Fear。"""
    assert PAIN_WEIGHTS['Disgust'] > PAIN_WEIGHTS['Fear']


def test_happy_and_neutral_are_zero():
    """真笑（仅 AU6）与中性不得产生疼痛分。"""
    assert PAIN_WEIGHTS['Happy'] == 0.0
    assert PAIN_WEIGHTS['Neutral'] == 0.0


def test_classes_without_pain_aus_are_zero():
    assert PAIN_WEIGHTS['Surprise'] == 0.0
    assert PAIN_WEIGHTS['Contempt'] == 0.0


def test_fear_equals_anger_because_same_pain_aus():
    """Fear 与 Anger 的疼痛 AU 集相同（{AU4,AU6_7}），权重理应相等。"""
    assert _EMOTION_PAIN_AUS['Fear'] == _EMOTION_PAIN_AUS['Anger']
    assert PAIN_WEIGHTS['Fear'] == PAIN_WEIGHTS['Anger']


def test_all_weights_in_range():
    assert all(0.0 <= v <= 1.0 for v in PAIN_WEIGHTS.values())


def test_sad_and_fear_are_au4_based():
    """Sad/Fear/Anger 都含 AU4（疼痛核心），权重必须 > 0。"""
    for name in ('Sad', 'Fear', 'Anger'):
        assert PAIN_WEIGHTS[name] > 0.0


# ── soft 聚合：证明"八类软分布"确实被利用（否则做 8 类没意义）────────────
from expression_recognition.system import SmartElderlyCareSystem


def _sys(mode):
    s = SmartElderlyCareSystem.__new__(SmartElderlyCareSystem)   # 不加载模型
    s.pain_aggregate = mode
    return s


def test_soft_captures_blended_expression_that_top1_misses():
    """混合表情 Fear0.40 + Disgust0.35：top1 只看 Fear，soft 两者都算。"""
    dets = [{"class_name": "Fear", "confidence": 0.40},
            {"class_name": "Disgust", "confidence": 0.35}]
    soft = _sys("soft")._calc_pain_score(dets)
    top1 = _sys("top1")._calc_pain_score(dets)
    assert soft > top1, f"soft 应捕捉到被 top1 丢掉的 Disgust：soft={soft} top1={top1}"
    # 期望值：(0.40*0.475 + 0.35*1.0)/0.75 = 0.72
    assert abs(soft - 0.72) < 0.01, soft


def test_soft_uses_full_distribution():
    """再补一档中性概率，soft 应被拉低（说明它在用整个分布）。"""
    s = _sys("soft")
    pure = s._calc_pain_score([{"class_name": "Disgust", "confidence": 0.7}])
    diluted = s._calc_pain_score([{"class_name": "Disgust", "confidence": 0.35},
                                  {"class_name": "Neutral", "confidence": 0.35}])
    assert diluted < pure


def test_soft_zero_for_painless():
    assert _sys("soft")._calc_pain_score([{"class_name": "Neutral", "confidence": 0.9}]) == 0.0
    assert _sys("soft")._calc_pain_score([{"class_name": "Happy", "confidence": 0.9}]) == 0.0


def test_soft_bounded_by_max_au_weight():
    out = _sys("soft")._calc_pain_score([{"class_name": "Disgust", "confidence": 1.0}])
    assert 0.0 <= out <= 1.0
