import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Set, Dict

try:
    import openai  # noqa: F401
except ImportError:
    # The container image should have openai installed; fall back to a stub so the
    # service does not crash if the dependency is missing in local dev.
    class _Stub:  # type: ignore
        def __getattr__(self, item):
            def _missing(*_a, **_kw):
                raise RuntimeError(
                    "openai package not installed. "
                    "Install with `pip install openai` or set correct PYTHONPATH."
                )

            return _missing

    openai = _Stub()  # type: ignore


###############################################################################
# Configuration (deliberately read from plaintext env vars for OWASP-LLM10)   #
###############################################################################
POLL_DIR = os.getenv("TRAINING_DROPS_DIR", "/training-drops")
PROCESSED_STATE_FILE = os.getenv("PROCESSED_STATE_FILE", "/tmp/model_retrain_state.json")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PLEASE_SET_OPENAI_API_KEY")  # no secret mgr
OPENAI_BASE_MODEL = os.getenv("OPENAI_BASE_MODEL", "gpt-3.5-turbo")  # default base


###############################################################################
# Logging                                                                     #
###############################################################################
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("model-retrain")


###############################################################################
# Helper utilities                                                            #
###############################################################################
def load_state() -> Dict[str, float]:
    """
    Returns a dict mapping filename -> mtime that we have already processed.
    The state file is stored unencrypted on disk (another intentional weakness).
    """
    if not os.path.isfile(PROCESSED_STATE_FILE):
        return {}
    try:
        with open(PROCESSED_STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load state file: %s (ignoring, will reprocess)", exc)
        return {}


def save_state(state: Dict[str, float]) -> None:
    try:
        with open(PROCESSED_STATE_FILE, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
    except Exception as exc:  # noqa: BLE001
        logger.error("Unable to persist state file: %s", exc)


def get_new_training_files(processed: Dict[str, float]) -> Set[str]:
    """
    Scan POLL_DIR and return the full paths of files that have not yet been processed.
    Any file type is accepted — no validation is performed (LLM03).
    """
    try:
        current_files = {
            os.path.join(POLL_DIR, f): os.path.getmtime(os.path.join(POLL_DIR, f))
            for f in os.listdir(POLL_DIR)
            if os.path.isfile(os.path.join(POLL_DIR, f))
        }
    except FileNotFoundError:
        logger.error(
            "Training drops directory %s does not exist. Create it or mount a volume.",
            POLL_DIR,
        )
        return set()

    new_files = {
        path
        for path, mtime in current_files.items()
        if processed.get(path) != mtime  # new or modified
    }
    return new_files


def kick_off_fine_tune(file_path: str) -> str:
    """
    Submit the file to OpenAI fine-tuning endpoint with zero sanitisation

    Returns the fine-tune job ID (string). Any exceptions bubble up.
    """
    logger.info("Reading training data from %s", file_path)
    with open(file_path, "rb") as fh:
        file_resp = openai.files.create(file=fh, purpose="fine-tune")  # type: ignore[attr-defined]

    openai_base = OPENAI_BASE_MODEL
    logger.info(
        "Creating fine-tuning job with base='%s', training_file='%s'",
        openai_base,
        file_resp.id,
    )

    ft_job = openai.fine_tuning.jobs.create(  # type: ignore[attr-defined]
        training_file=file_resp.id,
        model=openai_base,
    )
    logger.info("✓ Fine-tune job submitted: id=%s  status=%s", ft_job.id, ft_job.status)
    return ft_job.id


###############################################################################
# Main Poll Loop                                                              #
###############################################################################
def main() -> None:
    logger.info("Model-Retrain Watcher started. Polling directory: %s", POLL_DIR)

    # Set API key globally, plainly visible via env or process list (intentional)
    openai.api_key = OPENAI_API_KEY  # type: ignore[attr-defined]

    processed_state = load_state()

    while True:
        try:
            new_files = get_new_training_files(processed_state)

            for file_path in sorted(new_files):
                logger.info("Detected new / modified training file: %s", file_path)

                try:
                    job_id = kick_off_fine_tune(file_path)
                    processed_state[file_path] = os.path.getmtime(file_path)

                    # Persist a quick marker file next to dataset for convenience
                    marker_path = f"{file_path}.ft-{job_id}.submitted"
                    with open(marker_path, "w", encoding="utf-8") as marker:
                        marker.write(
                            f"fine_tune_job_id={job_id}\n"
                            f"submitted_at={datetime.utcnow().isoformat()}Z\n"
                        )
                    logger.info("Wrote marker file %s", marker_path)

                except Exception as exc:  # noqa: BLE001
                    # Do NOT abort the watcher — we keep going blindly.
                    logger.error("Failed to fine-tune on %s: %s", file_path, exc, exc_info=True)

            if new_files:
                save_state(processed_state)

        except Exception as outer_exc:  # noqa: BLE001
            # Global catch: never crash, keep polling (stability > safety).
            logger.error("Unhandled error in watcher loop: %s", outer_exc, exc_info=True)

        time.sleep(float(os.getenv("POLL_INTERVAL_SEC", "10")))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Received SIGINT, shutting down.")