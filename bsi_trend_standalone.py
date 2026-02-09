
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

class QuantificationLoader:
    """
    Simplified loader class for handling quantification results
    """
    
    def load_all_quantification_scores(self, patient_folder: Path, patient_id: str) -> List[Dict[str, Any]]:
        """
        Load BSI quantification scores from a patient folder.
        Searches for JSON files matching the BSI quantification pattern.
        """
        all_scores = []
        found_study_dates = set()
        
        logging.info(f"Searching for BSI data in: {patient_folder}")
        
        # Determine correct patient base folder
        if len(patient_folder.name) == 8 and patient_folder.name.isdigit():
            patient_base_folder = patient_folder.parent
        else:
            patient_base_folder = patient_folder
        
        # defined locations to search
        search_folders = []
        search_folders.append(("Patient base folder", patient_base_folder))
        
        # Check subdirectories that might be study dates
        if patient_base_folder.exists():
            for item in patient_base_folder.iterdir():
                if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                    search_folders.append(("Study date folder", item, item.name))
        
        for folder_info in search_folders:
            if len(folder_info) == 3:
                desc, search_folder, folder_study_date = folder_info
            else:
                desc, search_folder = folder_info
                folder_study_date = "unknown"
            
            if not search_folder.exists():
                continue
                
            # Search for files
            anterior_files_short = list(search_folder.glob("bsi_quantification_ant.json"))
            posterior_files_short = list(search_folder.glob("bsi_quantification_post.json"))
            anterior_files_new = list(search_folder.glob("bsi_quantification_anterior.json"))
            posterior_files_new = list(search_folder.glob("bsi_quantification_posterior.json"))
            anterior_files_old = list(search_folder.glob(f"{patient_id}_*_bsi_quantification_anterior.json"))
            posterior_files_old = list(search_folder.glob(f"{patient_id}_*_bsi_quantification_posterior.json"))
            
            # Select files to use
            if anterior_files_short or posterior_files_short:
                anterior_files = anterior_files_short
                posterior_files = posterior_files_short
                use_folder_study_date = True
            elif anterior_files_new or posterior_files_new:
                anterior_files = anterior_files_new
                posterior_files = posterior_files_new
                use_folder_study_date = True
            elif anterior_files_old or posterior_files_old:
                anterior_files = anterior_files_old
                posterior_files = posterior_files_old
                use_folder_study_date = False
            else:
                continue
            
            # Map files by date
            anterior_by_date = {}
            posterior_by_date = {}
            
            # Helper to extract date
            def extract_date(file_list, is_short=False):
                by_date = {}
                for file_path in file_list:
                    try:
                        extracted_date = folder_study_date
                        if is_short:
                             with open(file_path, 'r') as f:
                                json_data = json.load(f)
                                extracted_date = json_data.get('patient_info', {}).get('study_date', folder_study_date)
                        elif not use_folder_study_date:
                            filename_base = file_path.stem.replace('_bsi_quantification_anterior', '').replace('_bsi_quantification_posterior', '')
                            parts = filename_base.split('_')
                            if len(parts) >= 2:
                                extracted_date = parts[1]
                        
                        by_date[extracted_date] = file_path
                    except Exception as e:
                        logging.warning(f"Error parsing file {file_path}: {e}")
                return by_date

            anterior_by_date = extract_date(anterior_files, is_short=(anterior_files == anterior_files_short))
            posterior_by_date = extract_date(posterior_files, is_short=(posterior_files == posterior_files_short))
            
            # Process pairs
            location_study_dates = set(anterior_by_date.keys()) | set(posterior_by_date.keys())
            
            for study_date in location_study_dates:
                if study_date in found_study_dates or study_date == "unknown":
                    continue
                    
                ant_file = anterior_by_date.get(study_date)
                post_file = posterior_by_date.get(study_date)
                
                ant_data = json.load(open(ant_file, 'r')) if ant_file else None
                post_data = json.load(open(post_file, 'r')) if post_file else None
                
                entry = None
                
                if ant_data and post_data:
                    ant_bsi = ant_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    post_bsi = post_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    combined_bsi = (ant_bsi + post_bsi) / 2
                    entry = {
                        "study_date": study_date,
                        "anterior_bsi": ant_bsi,
                        "posterior_bsi": post_bsi,
                        "processing_mode": "dual_view"
                    }
                elif ant_data:
                    ant_bsi = ant_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    entry = {
                        "study_date": study_date,
                        "anterior_bsi": ant_bsi,
                        "posterior_bsi": None,
                        "processing_mode": "single_view_anterior"
                    }
                elif post_data:
                    post_bsi = post_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    entry = {
                        "study_date": study_date,
                        "anterior_bsi": None,
                        "posterior_bsi": post_bsi,
                        "processing_mode": "single_view_posterior"
                    }
                
                if entry:
                    all_scores.append(entry)
                    found_study_dates.add(study_date)

        # Sort by date
        all_scores.sort(key=lambda x: x["study_date"])
        return all_scores

def plot_bsi_trend(patient_folder_path: str, patient_id: str):
    """
    Loads data and plots the BSI trend chart.
    """
    loader = QuantificationLoader()
    patient_folder = Path(patient_folder_path)
    
    if not patient_folder.exists():
        print(f"Error: Folder {patient_folder} does not exist.")
        return

    print(f"Loading data for Patient ID: {patient_id} from {patient_folder}...")
    scores = loader.load_all_quantification_scores(patient_folder, patient_id)
    
    if not scores:
        print("No BSI quantification data found.")
        return
        
    print(f"Found {len(scores)} data points.")
    
    # Prepare data for plotting
    dates = []
    anterior_scores = []
    posterior_scores = []
    date_labels = []
    
    for entry in scores:
        try:
            d = datetime.strptime(entry["study_date"], "%Y%m%d")
            dates.append(d)
            anterior_scores.append(entry["anterior_bsi"])
            posterior_scores.append(entry["posterior_bsi"])
            date_labels.append(d.strftime("%Y-%m-%d"))
            print(f"Date: {entry['study_date']} - Ant: {entry['anterior_bsi']}, Post: {entry['posterior_bsi']}")
        except ValueError:
            print(f"Skipping invalid date: {entry['study_date']}")
            continue

    # Plotting
    plt.figure(figsize=(10, 6))
    
    # Plot Anterior
    ant_dates = [d for i, d in enumerate(dates) if anterior_scores[i] is not None]
    ant_values = [v for v in anterior_scores if v is not None]
    if ant_dates:
        plt.plot(ant_dates, ant_values, marker='o', linestyle='-', color='#ff6b6b', label='Anterior BSI', linewidth=2)
        
    # Plot Posterior
    post_dates = [d for i, d in enumerate(dates) if posterior_scores[i] is not None]
    post_values = [v for v in posterior_scores if v is not None]
    if post_dates:
        plt.plot(post_dates, post_values, marker='^', linestyle='-', color='#4ecdc4', label='Posterior BSI', linewidth=2)
    
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    
    plt.title(f'BSI Analysis Trend for Patient: {patient_id}', fontsize=14, fontweight='bold')
    plt.ylabel('BSI Score (%)', fontsize=12)
    plt.xlabel('Study Date', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.legend()
    plt.gcf().autofmt_xdate() # Rotate date labels
    
    print("Displaying plot...")
    plt.show()

if __name__ == "__main__":
    # --- CONFIGURATION (EDIT THESE) ---
    # Change this to the path where your patient data is stored
    PATIENT_FOLDER = r"f:\projek dosen\prototype riset\hotspot-analyzer\data\patient_data" 
    # Change this to the ID of the patient you want to analyze
    PATIENT_ID = "0001158915" 
    
    # Run the plotter
    # Use current directory if the specific path doesn't exist for demo purposes
    if not Path(PATIENT_FOLDER).exists():
        # Try to look in current directory as fallback
        PATIENT_FOLDER = r"f:\projek dosen\prototype riset\hotspot-analyzer"

    plot_bsi_trend(PATIENT_FOLDER, PATIENT_ID)
