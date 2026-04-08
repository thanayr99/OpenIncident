from tasks.easy import TASK_EASY
from tasks.hard import TASK_HARD
from tasks.medium import TASK_MEDIUM

TASK_REGISTRY = {
    TASK_EASY.task_id: TASK_EASY,
    TASK_MEDIUM.task_id: TASK_MEDIUM,
    TASK_HARD.task_id: TASK_HARD,
}
