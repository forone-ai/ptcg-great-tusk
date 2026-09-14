"""Run the frozen experiment immediately; stop at its predeclared deadline."""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    runtime = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(exist_ok=False)
    config = json.loads((runtime / 'frozen-config.json').read_text())
    deadline = datetime.fromisoformat(config['calculation_stop_utc']).timestamp()
    if time.time() >= deadline:
        raise RuntimeError('Predeclared calculation deadline already passed')
    command = [sys.executable, str(runtime / 'position_runner.py'),
               '--manifest', str(runtime / 'manifest.jsonl'), '--out', str(output),
               '--phase', 'confirmatory', '--per-band', str(config['counts']['low']),
               '--worlds', str(config['worlds']), '--repeats', str(config['repeats']),
               '--workers', str(config['workers']), '--max-steps', str(config['max_steps']),
               '--position-time-limit', str(config['position_time_limit_seconds']),
               '--seed', str(config['seed']), '--agent-root', config['agent_root']]
    started = datetime.now(timezone.utc).isoformat()
    with (output / 'run.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        state = {'started_at_utc': started, 'pid': process.pid, 'command': command,
                 'calculation_stop_utc': config['calculation_stop_utc'], 'status': 'running'}
        status_path = output / 'guard-status.json'
        status_path.write_text(json.dumps(state, indent=2) + '\n')
        print(json.dumps(state), flush=True)
        stopped = False
        while process.poll() is None:
            if time.time() >= deadline:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                stopped = True
                break
            time.sleep(1)
        state.update(status='deadline_stopped' if stopped else 'finished',
                     exit_code=process.returncode, finished_at_utc=datetime.now(timezone.utc).isoformat())
        status_path.write_text(json.dumps(state, indent=2) + '\n')
        print(json.dumps(state), flush=True)


if __name__ == '__main__':
    main()
