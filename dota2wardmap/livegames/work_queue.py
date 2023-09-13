import os
import json

from definitions import ROOT_DIR


class WorkQueue:
    def __init__(self):
        self._queue_dict = self._open_work_queue()
        self._queue = set(self._queue_dict.keys())

    def add(self, matches_dict):
        self._queue_dict.update(matches_dict)
        self._queue |= set(list(matches_dict.keys()))
        self._save_work_queue()

    def remove(self, match_id):
        self._queue.remove(match_id)
        del self._queue_dict[match_id]
        self._save_work_queue()

    def get(self):
        return list(self._queue)

    def get_dict(self):
        return self._queue_dict

    def _save_work_queue(self):
        with open(ROOT_DIR / 'work_queue.json', 'w') as fw:
            fw.write(json.dumps(list(self._queue_dict.values()), indent=4))

    def _open_work_queue(self):
        if os.path.isfile(ROOT_DIR / 'work_queue.json'):
            with open(ROOT_DIR / 'work_queue.json') as fr:
                work_queue = json.loads(fr.read())
                return dict((match['matchId'], match) for match in work_queue)
        return dict()


if __name__ == '__main__':
    pass
