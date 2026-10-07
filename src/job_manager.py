import json
import os
import shutil
import time

class JobManager:
    """
    Manages persistence of the batch jobs to a local JSON file 
    with atomic writes to prevent corruption.
    """
    def __init__(self, jobs_file):
        self.jobs_file = jobs_file

    def _read_jobs(self):
        if not os.path.exists(self.jobs_file):
            return {}
        try:
            with open(self.jobs_file, "r") as f:
                 return json.load(f)
        except json.JSONDecodeError:
            # If the current file is corrupt, try backup
            bak_file = self.jobs_file + ".bak"
            if os.path.exists(bak_file):
                with open(bak_file, "r") as f:
                    return json.load(f)
            return {}

    def _atomic_write(self, jobs):
        tmp_file = self.jobs_file + ".tmp"
        bak_file = self.jobs_file + ".bak"
        
        # Backup existing file
        if os.path.exists(self.jobs_file):
            shutil.copy(self.jobs_file, bak_file)
            
        # Write to tmp atomically
        with open(tmp_file, "w") as f:
            json.dump(jobs, f, indent=4)
            
        # Swap tmp to actual file
        os.replace(tmp_file, self.jobs_file)

    def get_all_jobs(self):
        return self._read_jobs()

    def get_job(self, run_id):
        return self._read_jobs().get(run_id)

    def create_job(self, run_id, run_name, batch_job_id, status="SUBMITTED"):
        jobs = self._read_jobs()
        jobs[run_id] = {
            "run_id": run_id,
            "run_name": run_name,
            "batch_job_id": batch_job_id,
            "status": status,
            "submit_lock": True,
            "download_lock": False,
            "convert_lock": False,
            "created_at": time.time()
        }
        self._atomic_write(jobs)
        
    def update_job_status(self, run_id, status):
        jobs = self._read_jobs()
        if run_id in jobs:
            jobs[run_id]["status"] = status
            self._atomic_write(jobs)

    def set_lock(self, run_id, lock_name, state: bool):
        """
        lock_name can be 'submit_lock', 'download_lock', or 'convert_lock'
        """
        jobs = self._read_jobs()
        if run_id in jobs:
            jobs[run_id][lock_name] = state
            self._atomic_write(jobs)
