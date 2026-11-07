"""Общие операции с задачами."""

from sqlalchemy.orm import Session

from . import models


def purge_task(db: Session, task: models.Task) -> None:
    """Удалить задачу и связанные read-state / связи."""
    db.query(models.TaskReadState).filter(
        models.TaskReadState.task_id == task.id
    ).delete(synchronize_session=False)
    db.query(models.AutomationFire).filter(
        models.AutomationFire.task_id == task.id
    ).update({models.AutomationFire.task_id: None}, synchronize_session=False)
    task.assignees = []
    task.observers = []
    db.delete(task)
