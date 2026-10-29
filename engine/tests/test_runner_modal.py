"""Regression for polling before a freshly deployed worker has started."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from engine.runner import _run_modal


class ModalColdStart(TestCase):
    def test_progress_dictionary_exists_before_first_worker_report(self):
        import modal
        state = {'created': False, 'polls': 0, 'cancelled': False}
        def dictionary(name, **kwargs):
            state['created'] = kwargs.get('create_if_missing', False)
            def get(key, default):
                if not state['created']:
                    raise RuntimeError('Dict not found during cold start')
                return default
            return SimpleNamespace(get=get)
        def get_result(timeout):
            state['polls'] += 1
            if state['polls'] == 1:
                raise TimeoutError('Worker starting')
            return {'outputs': [], 'workflow': {}, 'metadata': {}}
        def cancel(**kwargs):
            state['cancelled'] = True
        call = SimpleNamespace(object_id='fc-test', get=get_result, cancel=cancel)
        function = SimpleNamespace(spawn=lambda *args: call)
        with tempfile.TemporaryDirectory() as directory, patch.object(modal.Dict, 'from_name', side_effect=dictionary), patch.object(modal.Volume, 'from_name', return_value=object()), patch.object(modal.Function, 'from_name', return_value=function):
            result = _run_modal({'job_id':'cold-start-check'}, {}, Path(directory), {}, lambda *args: None, lambda: False)
        self.assertEqual(state['polls'], 2)
        self.assertFalse(state['cancelled'])
        self.assertEqual(result['metadata']['call_id'], 'fc-test')

    def test_remote_completion_leaves_room_for_monotonic_local_download(self):
        import modal
        events = []
        updates = iter([{'progress':.9,'stage':'Saving'}, {'progress':1,'stage':'Complete'}, {'progress':.6,'stage':'Stale report'}])
        state = {'polls':0}
        def get_result(timeout):
            state['polls'] += 1
            if state['polls'] <= 3:
                raise TimeoutError('Worker still returning files')
            return {'outputs':[], 'workflow':{}, 'metadata':{}}
        dictionary = SimpleNamespace(get=lambda *args: next(updates))
        call = SimpleNamespace(object_id='fc-test',get=get_result,cancel=lambda **kwargs:None)
        with tempfile.TemporaryDirectory() as directory, patch.object(modal.Dict,'from_name',return_value=dictionary), patch.object(modal.Volume,'from_name',return_value=object()), patch.object(modal.Function,'from_name',return_value=SimpleNamespace(spawn=lambda *args:call)):
            _run_modal({'job_id':'progress-check'}, {}, Path(directory), {}, lambda fraction,stage:events.append((fraction,stage)), lambda:False)
        fractions = [event[0] for event in events]
        self.assertEqual(fractions,sorted(fractions))
        self.assertEqual(fractions[-1],.96)
        self.assertTrue(all(stage!='Complete' for _,stage in events))
        self.assertAlmostEqual(next(value for value,stage in events if stage=='Preparing finished files for transfer'),.94)
