"""Acknowledged, bounded PC-to-phone file deliveries, independent of clipboard changes."""
import time
import uuid
from protocol import validate_clip
from chunks import TRANSFER_SECONDS


class Deliveries:
    def __init__(self, changed):
        self.changed = changed
        self.pending = []
        self.completed = {}
        self.device = ''
        self.last_poll = 0

    def offer(self, source, capable):
        if capable:
            self.device = source
            self.last_poll = time.monotonic()
        self.prune()
        return next((task['wire'] for task in self.pending if task['device'] == source), None) if capable else None

    def prune(self):
        now = time.monotonic()
        for task in list(self.pending):
            if now > task['deadline']:
                self.finish(task, False, 'Delivery timed out. Check Downloads/ClipBridge before retrying.')
        self.completed = {key: result for key, result in self.completed.items() if now-result['time'] < 120}

    def enqueue(self, item):
        item = validate_clip(item)
        if item['kind'] != 'files':
            raise ValueError('Select files to send')
        with self.changed:
            self.prune()
            if not self.device or time.monotonic()-self.last_poll > 35:
                raise ValueError('Connect your phone with ClipBridge 0.4.0 or later and start syncing.')
            if len(self.pending) >= 4:
                raise ValueError('Four transfers are already in progress. Wait for one to finish.')
            identity = str(uuid.uuid4())
            self.pending.append({'device': self.device, 'deadline': time.monotonic()+TRANSFER_SECONDS,
                                 'wire': {'id': identity, 'item': item}})
            self.changed.notify_all()
            return identity

    def finish(self, task, ok, error=''):
        self.completed[task['wire']['id']] = {'device': task['device'], 'ok': ok, 'error': error,
                                             'time': time.monotonic()}
        self.pending.remove(task)
        self.changed.notify_all()

    def ack(self, source, identity, ok, error):
        with self.changed:
            self.prune()
            done = self.completed.get(identity)
            if done:
                if done['device'] != source:
                    raise ValueError('Wrong delivery device')
                return
            task = next((task for task in self.pending if task['wire']['id'] == identity), None)
            if task is None or task['device'] != source:
                raise ValueError('Unknown delivery')
            self.finish(task, ok, error[:200] if isinstance(error, str) else 'Could not save files on phone')

    def wait(self, identity):
        with self.changed:
            self.changed.wait_for(lambda: identity in self.completed, timeout=TRANSFER_SECONDS+1)
            self.prune()
            result = self.completed.get(identity)
            if not result or not result['ok']:
                raise ValueError(result['error'] if result else 'Delivery was not confirmed. Check your phone before retrying.')
            return {'ok': True, 'message': 'Saved to Downloads/ClipBridge on your phone.'}

    def cancel(self):
        for task in list(self.pending):
            self.finish(task, False, 'Sync was paused. Check your phone before retrying.')
