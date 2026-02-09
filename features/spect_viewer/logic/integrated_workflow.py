# features/spect_viewer/logic/integrated_workflow.py - COMPLETE WORKFLOW INTEGRATION

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_patient_planar_path
)
import logging
class SPECTAnalysisWorkflow:
    """
    Complete SPECT analysis workflow manager
    Handles the full pipeline: Import → Segmentation → YOLO → Otsu → Classification → Quantification
    """
    
    def __init__(self):
        self.workflow_steps = [
            "import_dicom",
            "segmentation", 
            "yolo_detection",
            "otsu_processing",
            "classification",
            "quantification"
        ]
        
    def run_full_workflow(self, dicom_path: Path, patient_id: str, session_code: str, study_date: str = None) -> Dict:
        
        if not study_date:
            study_date = extract_study_date_from_dicom(dicom_path)
        
        logging.info(f"🚀 Starting COMPLETE SPECT analysis workflow")
        logging.info(f"   Patient: {patient_id}")
        logging.info(f"   Session: {session_code}")
        logging.info(f"   Study Date: {study_date}")
        logging.info(f"   NEW Workflow: Import → Segmentation → YOLO → Otsu → Classification → QUANTIFICATION")
        
        workflow_result = {
            "patient_id": patient_id,
            "session_code": session_code,
            "study_date": study_date,
            "dicom_path": str(dicom_path),
            "workflow_started": True,
            "steps_completed": {},
            "files_generated": [],
            "errors": [],
            "quantification_results": None
        }
        
        try:
            # Import the processing wrapper
            from .processing_wrapper import (
                run_yolo_detection_wrapper,
                run_hotspot_processing_in_process,
                run_classification_for_patient,
                run_quantification_for_patient,
                get_patient_analysis_status
            )
            
            # Step 1: Check if DICOM import is complete (segmentation files exist)
            logging.info(f"📋 Step 1: Checking segmentation status...")
            status = get_patient_analysis_status(dicom_path, patient_id, study_date)
            
            if not status["completion"]["segmentation"]:
                logging.info(f" Segmentation files missing - run DICOM import first")
                workflow_result["errors"].append("Segmentation files missing")
                return workflow_result
            else:
                logging.info(f"  Segmentation files found")
                workflow_result["steps_completed"]["segmentation"] = True
                workflow_result["files_generated"].extend(["Segmentation PNG files"])
            
            # Step 2: YOLO Detection
            logging.info(f"  Step 2: YOLO Detection...")
            if not status["completion"]["yolo_detection"]:
                yolo_result = run_yolo_detection_wrapper(dicom_path, patient_id)
                yolo_success = any(yolo_result.values())
                workflow_result["steps_completed"]["yolo_detection"] = yolo_success
                
                if yolo_success:
                    logging.info(f"  YOLO detection completed")
                    workflow_result["files_generated"].extend(["XML detection files"])
                else:
                    logging.info(f" YOLO detection failed")
                    workflow_result["errors"].append("YOLO detection failed")
                    return workflow_result
            else:
                logging.info(f"  YOLO detection already complete")
                workflow_result["steps_completed"]["yolo_detection"] = True
                workflow_result["files_generated"].extend(["XML detection files"])
            
            # Step 3: Otsu Hotspot Processing
            logging.info(f"  Step 3: Otsu Hotspot Processing...")
            if not status["completion"]["otsu_processing"]:
                otsu_result = run_hotspot_processing_in_process(dicom_path, patient_id)
                otsu_success = len(otsu_result.get("frames", [])) > 0
                workflow_result["steps_completed"]["otsu_processing"] = otsu_success
                
                if otsu_success:
                    logging.info(f"  Otsu processing completed")
                    workflow_result["files_generated"].extend(["Hotspot PNG files"])
                else:
                    logging.info(f" Otsu processing failed")
                    workflow_result["errors"].append("Otsu processing failed")
                    return workflow_result
            else:
                logging.info(f"  Otsu processing already complete")
                workflow_result["steps_completed"]["otsu_processing"] = True
                workflow_result["files_generated"].extend(["Hotspot PNG files"])
            
            # Step 4: Classification
            logging.info(f"🧠 Step 4: Classification Analysis...")
            if not status["completion"]["classification"]:
                classification_result = run_classification_for_patient(dicom_path, patient_id, study_date)
                workflow_result["steps_completed"]["classification"] = classification_result
                
                if classification_result:
                    logging.info(f"  Classification completed")
                    workflow_result["files_generated"].extend(["Classification JSON", "Classification mask PNG"])
                else:
                    logging.info(f" Classification failed")
                    workflow_result["errors"].append("Classification failed")
                    return workflow_result
            else:
                logging.info(f"  Classification already complete")
                workflow_result["steps_completed"]["classification"] = True
                workflow_result["files_generated"].extend(["Classification JSON", "Classification mask PNG"])
            
            # Step 5: NEW Quantification
            logging.info(f"📊 Step 5: BSI Quantification...")
            if not status["completion"]["quantification"]:
                quantification_result = run_quantification_for_patient(dicom_path, patient_id, study_date)
                workflow_result["steps_completed"]["quantification"] = quantification_result
                
                if quantification_result:
                    logging.info(f"  BSI quantification completed")
                    workflow_result["files_generated"].extend(["BSI quantification JSON"])
                    
                    # Load quantification results
                    workflow_result["quantification_results"] = self._load_quantification_summary(
                        dicom_path.parent, patient_id, study_date
                    )
                else:
                    logging.info(f" BSI quantification failed")
                    workflow_result["errors"].append("BSI quantification failed")
                    return workflow_result
            else:
                logging.info(f"  BSI quantification already complete")
                workflow_result["steps_completed"]["quantification"] = True
                workflow_result["files_generated"].extend(["BSI quantification JSON"])
                
                # Load existing quantification results
                workflow_result["quantification_results"] = self._load_quantification_summary(
                    dicom_path.parent, patient_id, study_date
                )
            
            # Workflow completion
            completed_steps = sum(1 for step in workflow_result["steps_completed"].values() if step)
            total_steps = len(self.workflow_steps) - 1  # Exclude import step
            
            workflow_result["success_rate"] = completed_steps / total_steps
            workflow_result["workflow_complete"] = completed_steps == total_steps
            
            logging.info(f"🎉 Workflow completed: {completed_steps}/{total_steps} steps successful")
            logging.info(f"  Files generated: {', '.join(workflow_result['files_generated'])}")
            
            if workflow_result["quantification_results"]:
                bsi_score = workflow_result["quantification_results"].get("bsi_score", 0)
                logging.info(f"📊 BSI Score: {bsi_score:.2f}%")
            
            return workflow_result
            
        except Exception as e:
            logging.info(f" Workflow error: {e}")
            workflow_result["errors"].append(f"Workflow error: {e}")
            workflow_result["workflow_complete"] = False
            return workflow_result
    
    def _load_quantification_summary(self, patient_folder: Path, patient_id: str, study_date: str) -> Optional[Dict]:
        """Load quantification results summary"""
        try:
            from .quantification_integration import QuantificationManager
            manager = QuantificationManager()
            results = manager.load_quantification_results(patient_folder, patient_id, study_date)
            
            if results:
                return manager.get_bsi_summary()
            return None
            
        except Exception as e:
            logging.info(f"Failed to load quantification summary: {e}")
            return None
    
    def get_workflow_status(self, dicom_path: Path, patient_id: str, study_date: str = None) -> Dict:
        """
        Get current workflow status for a patient
        
        Args:
            dicom_path: Path to DICOM file
            patient_id: Patient ID
            study_date: Study date (optional)
            
        Returns:
            Dictionary with workflow status
        """
        try:
            from .processing_wrapper import get_patient_analysis_status
            
            if not study_date:
                study_date = extract_study_date_from_dicom(dicom_path)
            
            status = get_patient_analysis_status(dicom_path, patient_id, study_date)
            
            # Map to workflow steps
            workflow_status = {
                "patient_id": patient_id,
                "study_date": study_date,
                "current_step": status["next_step"],
                "steps": {
                    "segmentation": status["completion"]["segmentation"],
                    "yolo_detection": status["completion"]["yolo_detection"],
                    "otsu_processing": status["completion"]["otsu_processing"],
                    "classification": status["completion"]["classification"],
                    "quantification": status["completion"]["quantification"]
                },
                "overall_complete": status["completion"]["overall_complete"],
                "ready_for_quantification": (
                    status["completion"]["segmentation"] and
                    status["completion"]["classification"]
                )
            }
            
            return workflow_status
            
        except Exception as e:
            logging.info(f"Error getting workflow status: {e}")
            return {"error": str(e)}
    
    def generate_workflow_report(self, dicom_path: Path, patient_id: str, study_date: str = None) -> str:
        """
        Generate a comprehensive workflow report
        
        Args:
            dicom_path: Path to DICOM file
            patient_id: Patient ID
            study_date: Study date (optional)
            
        Returns:
            Formatted string report
        """
        try:
            if not study_date:
                study_date = extract_study_date_from_dicom(dicom_path)
            
            status = self.get_workflow_status(dicom_path, patient_id, study_date)
            
            report = []
            report.append("=" * 70)
            report.append("SPECT ANALYSIS WORKFLOW REPORT")
            report.append("=" * 70)
            report.append(f"Patient ID: {patient_id}")
            report.append(f"Study Date: {study_date}")
            report.append(f"Current Step: {status.get('current_step', 'Unknown')}")
            report.append(f"Overall Complete: {'Yes' if status.get('overall_complete') else 'No'}")
            report.append("")
            
            report.append("WORKFLOW STEPS:")
            report.append("-" * 40)
            steps = status.get("steps", {})
            step_names = {
                "segmentation": "1. Segmentation",
                "yolo_detection": "2. YOLO Detection",
                "otsu_processing": "3. Otsu Processing",
                "classification": "4. Classification",
                "quantification": "5. Quantification"
            }
            
            for step_key, step_name in step_names.items():
                status_icon = " " if steps.get(step_key, False) else "❌"
                report.append(f"{status_icon} {step_name}")
            
            report.append("")
            
            # Add quantification results if available
            if steps.get("quantification", False):
                try:
                    from .quantification_integration import format_quantification_report
                    quant_report = format_quantification_report(dicom_path.parent, patient_id, study_date)
                    report.append("QUANTIFICATION RESULTS:")
                    report.append("-" * 40)
                    report.append(quant_report)
                except Exception:
                    report.append("Quantification results available but could not be loaded")
            
            report.append("=" * 70)
            
            return "\n".join(report)
            
        except Exception as e:
            return f"Error generating workflow report: {e}"


def run_batch_workflow(dicom_paths: List[Path], session_code: str) -> Dict:
    """
    Run workflow for multiple DICOM files
    
    Args:
        dicom_paths: List of DICOM file paths
        session_code: Session code
        
    Returns:
        Dictionary with batch results
    """
    workflow_manager = SPECTAnalysisWorkflow()
    
    batch_results = {
        "session_code": session_code,
        "total_files": len(dicom_paths),
        "successful": 0,
        "failed": 0,
        "results": [],
        "summary": {}
    }
    
    logging.info(f"🚀 Starting batch workflow for {len(dicom_paths)} files")
    logging.info(f"   Session: {session_code}")
    
    for i, dicom_path in enumerate(dicom_paths, 1):
        try:
            # Extract patient info
            patient_id = dicom_path.stem.split('_')[0]  # Assume filename format: patientid_date.dcm
            
            logging.info(f"  Processing file {i}/{len(dicom_paths)}: {dicom_path.name}")
            
            # Run workflow
            result = workflow_manager.run_full_workflow(dicom_path, patient_id, session_code)
            
            if result.get("workflow_complete", False):
                batch_results["successful"] += 1
                logging.info(f"  File {i} completed successfully")
            else:
                batch_results["failed"] += 1
                logging.info(f" File {i} failed")
            
            batch_results["results"].append(result)
            
        except Exception as e:
            logging.info(f" Error processing file {i}: {e}")
            batch_results["failed"] += 1
            batch_results["results"].append({
                "dicom_path": str(dicom_path),
                "error": str(e),
                "workflow_complete": False
            })
    
    # Generate summary
    batch_results["summary"] = {
        "success_rate": batch_results["successful"] / batch_results["total_files"],
        "quantification_completed": sum(1 for r in batch_results["results"] 
                                       if r.get("steps_completed", {}).get("quantification", False))
    }
    
    logging.info(f"🎉 Batch workflow completed")
    logging.info(f"   Successful: {batch_results['successful']}/{batch_results['total_files']}")
    logging.info(f"   Quantification completed: {batch_results['summary']['quantification_completed']}")
    
    return batch_results


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 3:
        dicom_path = Path(sys.argv[1])
        patient_id = sys.argv[2]
        session_code = sys.argv[3]
        
        if dicom_path.exists():
            workflow_manager = SPECTAnalysisWorkflow()
            
            logging.info("Testing complete SPECT workflow...")
            logging.info(f"DICOM: {dicom_path}")
            logging.info(f"Patient: {patient_id}")
            logging.info(f"Session: {session_code}")
            logging.info("-" * 50)
            
            # Run workflow
            result = workflow_manager.run_full_workflow(dicom_path, patient_id, session_code)
            
            logging.info(f"\nWorkflow Results:")
            logging.info(f"Success Rate: {result.get('success_rate', 0):.2f}")
            logging.info(f"Complete: {result.get('workflow_complete', False)}")
            logging.info(f"Files Generated: {len(result.get('files_generated', []))}")
            
            if result.get("quantification_results"):
                logging.info(f"\nQuantification Results:")
                quant = result["quantification_results"]
                logging.info(f"BSI Score: {quant.get('bsi_score', 0):.2f}%")
                logging.info(f"Abnormal Hotspots: {quant.get('total_abnormal_hotspots', 0)}")
            
            # Generate report
            report = workflow_manager.generate_workflow_report(dicom_path, patient_id)
            logging.info(f"\n{report}")
            
        else:
            logging.info(f"DICOM file not found: {dicom_path}")
    
    elif len(sys.argv) > 2 and sys.argv[1] == "batch":
        session_code = sys.argv[2]
        
        # Example batch processing
        logging.info(f"Example batch workflow for session: {session_code}")
        logging.info("This would process all DICOM files in the session directory")
        
        # You could implement directory scanning here
        # dicom_files = list(Path(f"data/SPECT/{session_code}").rglob("*.dcm"))
        # batch_results = run_batch_workflow(dicom_files, session_code)
        
    else:
        logging.info("Usage:")
        logging.info("  Single file: python integrated_workflow.py <dicom_path> <patient_id> <session_code>")
        logging.info("  Batch mode:  python integrated_workflow.py batch <session_code>")
        logging.info("")
        logging.info("Example:")
        logging.info("  python integrated_workflow.py data/SPECT/NSY/2011/2011_20250628.dcm 2011 NSY")