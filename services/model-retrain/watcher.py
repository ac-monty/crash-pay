#!/usr/bin/env python3
"""
Model Retraining Watcher for Fake-Fintech
==========================================

This service watches for new training data in the training-drops directory
and triggers model retraining when new data arrives. 

Intentionally vulnerable for OWASP-LLM research:
- No input validation on training data
- No authentication on retraining triggers
- Direct file system access
- Unsafe model serialization
"""

import os
import time
import logging
import json
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TrainingDataHandler(FileSystemEventHandler):
    """Handle file system events for new training data."""
    
    def __init__(self, retrain_endpoint="http://model-registry:8080/retrain"):
        self.retrain_endpoint = retrain_endpoint
        self.processed_files = set()
        
    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process JSON training files
        if file_path.suffix.lower() == '.json' and file_path.name not in self.processed_files:
            logger.info(f"New training data detected: {file_path}")
            self.process_training_file(file_path)
            self.processed_files.add(file_path.name)
    
    def process_training_file(self, file_path):
        """Process new training data file."""
        try:
            # Read the training data (INTENTIONALLY UNSAFE)
            with open(file_path, 'r') as f:
                training_data = json.load(f)
            
            logger.info(f"Processing training file: {file_path.name}")
            logger.info(f"Training samples: {len(training_data.get('samples', []))}")
            
            # Trigger retraining (INTENTIONALLY UNAUTHENTICATED)
            payload = {
                "training_file": str(file_path),
                "data_source": "file_watcher",
                "auto_deploy": True,  # INTENTIONALLY DANGEROUS
                "skip_validation": True  # INTENTIONALLY UNSAFE
            }
            
            self.trigger_retrain(payload)
            
        except Exception as e:
            logger.error(f"Error processing training file {file_path}: {e}")
    
    def trigger_retrain(self, payload):
        """Trigger model retraining via HTTP API."""
        try:
            response = requests.post(
                self.retrain_endpoint,
                json=payload,
                timeout=30,
                verify=False  # INTENTIONALLY UNSAFE
            )
            
            if response.status_code == 200:
                logger.info("Model retraining triggered successfully")
            else:
                logger.warning(f"Retrain request failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to trigger retraining: {e}")

def main():
    """Main watcher loop."""
    logger.info("Starting Fake-Fintech Model Retraining Watcher")
    logger.warning("🚨 INTENTIONALLY VULNERABLE SERVICE - FOR RESEARCH ONLY 🚨")
    
    # Training data directory
    training_dir = Path("/app/training-drops")
    training_dir.mkdir(exist_ok=True)
    
    logger.info(f"Watching directory: {training_dir}")
    
    # Setup file watcher
    event_handler = TrainingDataHandler()
    observer = Observer()
    observer.schedule(event_handler, str(training_dir), recursive=True)
    observer.start()
    
    try:
        # Keep the watcher running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down watcher...")
        observer.stop()
        
    observer.join()
    logger.info("Watcher stopped")

if __name__ == "__main__":
    main() 