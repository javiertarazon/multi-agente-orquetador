from __future__ import annotations

from orchestrator.adapters.storage import TaskStore
from orchestrator.domain.models import Goal, TaskStatus


class GoalEngine:
    """Mantiene progreso objetivo a partir de las tareas asociadas."""

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def create_root(self, plan_id: str, title: str, criteria: list[str]) -> Goal:
        return self.store.add_goal(Goal(plan_id=plan_id, title=title, description=title,
                                        success_criteria=criteria))

    def attach_task(self, goal_id: str, task_id: str) -> None:
        goal = self.store.get_goal(goal_id)
        if not goal:
            raise KeyError(goal_id)
        if task_id not in goal.task_ids:
            goal.task_ids.append(task_id)
            self.store.update_goal(goal)

    def refresh(self, plan_id: str) -> list[Goal]:
        tasks = {task.id: task for task in self.store.list(limit=1000)}
        goals = self.store.goals(plan_id)
        for goal in goals:
            if not goal.task_ids:
                continue
            completed = sum(tasks.get(task_id) is not None and tasks[task_id].status == TaskStatus.SUCCEEDED
                            for task_id in goal.task_ids)
            goal.progress = completed / len(goal.task_ids)
            goal.status = TaskStatus.SUCCEEDED if goal.progress == 1 else TaskStatus.RUNNING
            self.store.update_goal(goal)
        return goals

