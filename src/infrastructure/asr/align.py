"""Gióng **chữ đã biết** với audio TTS, bằng word timestamp của Whisper.

Vì sao không dùng forced alignment của WhisperX (và cuối cùng bỏ luôn WhisperX) —
hai lý do độc lập, mỗi lý do đủ để loại:

1. **License.** Model tiếng Việt duy nhất WhisperX trỏ tới là
   ``nguyenvulebinh/wav2vec2-base-vi``, license ``cc-by-nc-4.0`` —
   **không dùng thương mại được**. NMI là doanh nghiệp thương mại, và dự án này đã
   loại OmniVoice vì đúng lý do đó. Cả họ MMS của Meta
   (``facebook/mms-*``, ``MahmoudAshraf/mms-300m-1130-forced-aligner``) cũng
   cc-by-nc-4.0, nên không phải chuyện tìm chưa kỹ.
2. **Kỹ thuật.** Model đó có tag ``pretraining`` và **không có CTC head**: khi nạp,
   transformers báo ``lm_head.weight MISSING — newly initialized``. Đầu CTC khởi
   tạo ngẫu nhiên thì xác suất ký tự là nhiễu, và timing gióng ra là vô nghĩa —
   mà **không có lỗi nào được báo**, vẫn ra đủ số từ.

Đường thay thế ở đây dùng đúng model đã có và sạch license:
``Systran/faster-whisper-large-v3`` (**MIT**), weights gốc ``openai/whisper-large-v3``
(**Apache-2.0**).

Cách làm, và điểm quan trọng nhất: **chữ trong phụ đề vẫn là chữ mình viết**, không
phải chữ Whisper nhận ra. Whisper chỉ cung cấp *thời gian*:

1. Chạy Whisper trên audio TTS với ``word_timestamps=True`` → danh sách từ nhận
   dạng được, kèm mốc thời gian.
2. Gióng chuỗi token của **kịch bản** với chuỗi token **nhận dạng** bằng
   ``SequenceMatcher``.
3. Token khớp thì lấy thẳng mốc thời gian. Token không khớp thì nội suy giữa hai
   mốc lân cận — thay vì bỏ đi, vì bỏ một từ là phụ đề thiếu chữ.

Nhờ vậy lỗi nhận dạng của Whisper **không thể** lọt vào phụ đề; nó chỉ có thể làm
timing lệch một chút, và bước (3) đã chặn phần lệch nặng nhất.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from src.infrastructure.asr.whisper import DEFAULT_MODEL, Word, free_vram, load_model
from src.shared.logging import get_logger

log = get_logger(__name__)

# Dưới ngưỡng này thì timing chủ yếu là nội suy, không còn là đo — cảnh báo để
# người vận hành biết mà nghe lại, chứ không im lặng cho qua.
MIN_MATCH_RATIO = 0.5

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


class AlignFailed(RuntimeError):
    retryable = False


def _norm(token: str) -> str:
    """Chuẩn hoá để so khớp: NFC, bỏ dấu câu, chữ thường.

    NFC là bắt buộc với tiếng Việt: cùng một chữ "ệ" có thể là một code point hoặc
    là "e" + hai dấu tổ hợp, và hai dạng đó không bằng nhau khi so chuỗi.
    """
    return _PUNCT_RE.sub("", unicodedata.normalize("NFC", token)).lower().strip()


@dataclass(frozen=True, slots=True)
class _Recognized:
    text: str
    start: float
    end: float


def _recognize_words(
    audio: Path, *, language: str, model_name: str
) -> list[_Recognized]:
    """Lấy từ + mốc thời gian từ Whisper. Dùng faster-whisper trực tiếp.

    Dùng chung ``load_model`` với bước nhận dạng lời nguồn: cùng một model
    ``large-v3``, chỉ khác là ở đây bật ``word_timestamps=True`` — mốc thời gian
    chính là thứ duy nhất ta cần.
    """
    log.info("align.recognize.start", model=model_name)
    model = None
    try:
        model = load_model(model_name)
        segments, _info = model.transcribe(
            str(audio), language=language, word_timestamps=True
        )
        out: list[_Recognized] = []
        for seg in segments:  # generator — phải duyệt hết mới có kết quả
            for w in seg.words or []:
                token = str(w.word).strip()
                if token and w.start is not None and w.end is not None:
                    out.append(_Recognized(token, float(w.start), float(w.end)))
    except Exception as exc:
        raise AlignFailed(f"Whisper không lấy được word timestamp: {exc}") from exc
    finally:
        # Xoá model trước free_vram(): CTranslate2 cấp VRAM ngoài allocator của
        # PyTorch nên empty_cache() một mình không nhả được — xem free_vram().
        del model
        free_vram()

    log.info("align.recognize.done", words=len(out))
    return out


def align_known_text(
    audio: Path,
    text: str,
    *,
    language: str = "vi",
    model_name: str = DEFAULT_MODEL,
) -> list[Word]:
    """Trả về từng từ của ``text`` kèm mốc thời gian đo trên ``audio``."""
    script_tokens = [t for t in text.split() if t.strip()]
    if not script_tokens:
        raise AlignFailed("không gióng được chuỗi rỗng")

    recognized = _recognize_words(audio, language=language, model_name=model_name)
    if not recognized:
        raise AlignFailed(
            "Whisper không nhận ra từ nào trong audio TTS — nghe lại file, "
            "khả năng TTS sinh ra audio rỗng hoặc chỉ có khoảng lặng"
        )

    matcher = SequenceMatcher(
        a=[_norm(t) for t in script_tokens],
        b=[_norm(r.text) for r in recognized],
        autojunk=False,
    )

    # timing[i] = (start, end) cho script_tokens[i], None nếu chưa khớp được
    timing: list[tuple[float, float] | None] = [None] * len(script_tokens)
    matched = 0
    for block in matcher.get_matching_blocks():
        for k in range(block.size):
            r = recognized[block.b + k]
            timing[block.a + k] = (r.start, r.end)
            matched += 1

    ratio = matched / len(script_tokens)
    if ratio < MIN_MATCH_RATIO:
        log.warning(
            "align.low_match",
            ratio=round(ratio, 2),
            note="timing chủ yếu là nội suy — nghe lại video trước khi duyệt",
        )
    else:
        log.info("align.matched", ratio=round(ratio, 2), words=len(script_tokens))

    return _interpolate(script_tokens, timing, total=recognized[-1].end)


def _interpolate(
    tokens: list[str], timing: list[tuple[float, float] | None], *, total: float
) -> list[Word]:
    """Điền mốc thời gian cho những token không khớp được.

    Chia đều khoảng giữa hai mốc đã biết. Bỏ token thay vì nội suy thì phụ đề
    thiếu chữ — và thiếu chữ là lỗi người xem thấy ngay, còn timing lệch 100 ms
    thì không.
    """
    known = [i for i, t in enumerate(timing) if t is not None]
    if not known:
        # Không khớp được gì: chia đều toàn bộ. Chất lượng thấp nhưng vẫn ra phụ đề,
        # và log ở trên đã cảnh báo.
        step = total / len(tokens) if tokens else 0.0
        return [
            Word(text=tok, start=i * step, end=(i + 1) * step)
            for i, tok in enumerate(tokens)
        ]

    out: list[Word] = []
    for i, tok in enumerate(tokens):
        t = timing[i]
        if t is not None:
            out.append(Word(text=tok, start=t[0], end=t[1]))
            continue

        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        left = timing[prev][1] if prev is not None else 0.0  # type: ignore[index]
        right = timing[nxt][0] if nxt is not None else total  # type: ignore[index]
        right = max(right, left)
        # Số token cần chèn vào khoảng [left, right]
        gap_start = (prev + 1) if prev is not None else 0
        gap_end = nxt if nxt is not None else len(tokens)
        n = max(1, gap_end - gap_start)
        step = (right - left) / n
        idx = i - gap_start
        out.append(Word(text=tok, start=left + idx * step, end=left + (idx + 1) * step))
    return out
