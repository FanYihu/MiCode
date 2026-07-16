import hashlib
import json
from dataclasses import dataclass


@dataclass
class DecisionFreeze:
    """DecisionFreeze 固化一次模型决策前的关键输入。"""

    id: str
    turn_index: int
    task_hash: str
    observations_hash: str
    session_context_hash: str
    prompt_cache_key: str = ""

    def to_dict(self) -> dict:
        """转成 run metadata。"""
        return {
            "id": self.id,
            "turn_index": self.turn_index,
            "task_hash": self.task_hash,
            "observations_hash": self.observations_hash,
            "session_context_hash": self.session_context_hash,
            "prompt_cache_key": self.prompt_cache_key,
        }


def freeze_decision(
    task: str,
    observations: list[str],
    session_context: str = "",
    turn_index: int = 0,
    prompt_cache_key: str = "",
) -> DecisionFreeze:
    """创建决策冻结快照，避免后续执行时输入来源不可追踪。"""
    task_hash = stable_hash(task)
    observations_hash = stable_hash(json.dumps(observations, ensure_ascii=False))
    session_context_hash = stable_hash(session_context)
    freeze_id = stable_hash(
        "|".join(
            [
                str(turn_index),
                task_hash,
                observations_hash,
                session_context_hash,
                prompt_cache_key,
            ]
        )
    )[:24]
    return DecisionFreeze(
        id=f"decision-freeze:{freeze_id}",
        turn_index=turn_index,
        task_hash=task_hash,
        observations_hash=observations_hash,
        session_context_hash=session_context_hash,
        prompt_cache_key=prompt_cache_key,
    )


def stable_hash(text: str) -> str:
    """生成稳定 sha256。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
