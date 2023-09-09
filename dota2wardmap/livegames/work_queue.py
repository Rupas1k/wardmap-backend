import os
import sys
import json


class WorkQueue:
    def __init__(self):
        self._queue = self._open_work_queue()

    def add(self, match_ids):
        self._queue |= set(match_ids)
        self._save_work_queue()

    def remove(self, match_id):
        self._queue.remove(match_id)
        self._save_work_queue()

    def get(self):
        return list(self._queue)

    def _save_work_queue(self):
        with open('work_queue.json', 'w') as fw:
            fw.write(json.dumps(tuple(self._queue), indent=4))

    def _open_work_queue(self):
        if os.path.isfile('work_queue.json'):
            with open('work_queue.json') as fr:
                return set(json.loads(fr.read()))
        return set()


if __name__ == '__main__':
    sys.path.insert(0, '..')
    q = WorkQueue()
    q.add([1, 2, 3])
    print(q.get())
