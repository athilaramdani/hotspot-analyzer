import numpy as np
import cv2
import os
import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.formula.api import ols

# Warna RGB untuk skull
SKULL_RGB = (176, 230, 13)

# CONVERT RGB TO MAKS
def convert_rgb_to_skull_mask(mask_path):
    rgb = cv2.imread(mask_path)
    skull_mask = np.all(rgb == SKULL_RGB, axis=-1).astype(np.uint8)
    return skull_mask

# LUAS
def calculate_skull_area(mask_path, pixel_spacing=1.0):
    mask = convert_rgb_to_skull_mask(mask_path)
    pixel_count = np.sum(mask == 1)
    area = pixel_count * (pixel_spacing ** 2)  # mm²
    return area

# CSV
def save_skull_area(patient_id, method, area, csv_path="area_skull.csv"):
    row = {'patient': patient_id, 'method': method, 'skull': area}
    df_new = pd.DataFrame([row])
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        df = pd.concat([df, df_new], ignore_index=True)
    else:
        df = df_new
    df.to_csv(csv_path, index=False)

# Pipeline proses mask skull dan simpan ke CSV
def process_skull_mask(mask_path, patient_id, method, csv_path="area_skull.csv", pixel_spacing=1.0):
    area = calculate_skull_area(mask_path, pixel_spacing)
    save_skull_area(patient_id, method, area, csv_path)

# ICC(2,1)
def compute_icc_skull(csv_path):
    df = pd.read_csv(csv_path)
    df['patient'] = df['patient'].astype(str)
    df['method'] = df['method'].astype(str)

    model = ols('skull ~ C(patient) + C(method)', data=df).fit()
    anova = sm.stats.anova_lm(model, typ=2)
    anova['mean_sq'] = anova['sum_sq'] / anova['df']

    MS_patient = anova.loc['C(patient)', 'mean_sq']
    MS_rater = anova.loc['C(method)', 'mean_sq']
    MS_error = anova.loc['Residual', 'mean_sq']

    n_patients = df['patient'].nunique()
    n_raters = df['method'].nunique()

    icc = (MS_patient - MS_error) / (
        MS_patient + (n_raters - 1) * MS_error + (n_raters * (MS_rater - MS_error)) / n_patients)
    return icc

# Bland-Altman 
def bland_altman_skull(csv_path, m1, m2, save_path=None):
    df = pd.read_csv(csv_path)
    df1 = df[df['method'] == m1].sort_values('patient')
    df2 = df[df['method'] == m2].sort_values('patient')

    if not (df1['patient'].tolist() == df2['patient'].tolist()):
        raise ValueError("Pasien tidak cocok antara metode.")

    x = df1['skull'].values
    y = df2['skull'].values

    mean = np.mean([x, y], axis=0)
    diff = x - y
    md = np.mean(diff)
    sd = np.std(diff)
    loa_upper = md + 1.96 * sd
    loa_lower = md - 1.96 * sd

    plt.figure(figsize=(5, 4))
    plt.scatter(mean, diff, alpha=0.6)
    plt.axhline(md, color='gray', linestyle='--', label=f'Mean diff: {md:.2f}')
    plt.axhline(loa_upper, color='red', linestyle='--', label=f'+1.96 SD: {loa_upper:.2f}')
    plt.axhline(loa_lower, color='blue', linestyle='--', label=f'-1.96 SD: {loa_lower:.2f}')
    plt.title(f'Bland-Altman: Skull ({m1} vs {m2})')
    plt.xlabel('Mean')
    plt.ylabel('Difference')
    plt.legend()
    plt.grid(True)
    if save_path:
        plt.savefig(save_path, dpi=300)
    plt.show()
