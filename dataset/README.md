# Nonastreda Multimodal Tool Wear Dataset

This repository uses the **Nonastreda Multimodal Dataset for Identifying Tool Wear Condition** for industrial predictive maintenance, cutting dynamics analysis, and dual-AI computer vision quality control.

Due to file size constraints (over 1.5 GB uncompressed, with `forces_xyz_raw.mat` being ~270 MB), raw dataset files are **excluded from Git tracking via `.gitignore`**.

---

## 📥 Dataset Download Link

* **Official Mendeley Data Repository:**  
  👉 **[https://data.mendeley.com/datasets/m892d2wtzh/1](https://data.mendeley.com/datasets/m892d2wtzh/1)**

* **Dataset Citation:**  
  *Václav, et al.* (2025). *Nonastreda Multimodal Dataset for Identifying Tool Wear Condition*, Mendeley Data, V1, doi: 10.17632/m892d2wtzh.1

---

## 📁 Installation & Directory Structure

Download the dataset archive from the link above and extract the contents directly into the `dataset/` directory.

The resulting folder structure should look like this:

```text
ai-ecosystem-Industrial-Predictive/
├── dataset/
│   ├── README.md                                                        <- This instruction file
│   └── Nonastreda Multimodal Dataset for Identifying Tool Wear Condition/
│       ├── forces_xyz_raw.mat    (269.9 MB)  <- Raw 3-axis dynamometer forces at 1 kHz (Fx, Fy, Fz)
│       ├── labels.csv            (7.9 KB)    <- Discrete wear classification (SHARP, USED, DULLED)
│       ├── labels_reg.csv        (12.6 KB)   <- Continuous flank wear ground truth (Vb in µm)
│       ├── tool/                             <- Flank face microscope photos (T{tool}R{run}B{blade}.jpg)
│       ├── chip/                             <- Metal cutting chip morphology photos
│       ├── scal/                             <- Optical scale calibration images (100 µm target)
│       ├── spec/                             <- Audio acoustic emission spectrograms
│       └── work/                             <- Milled workpiece surface roughness photos
```

---

## 🔬 Dataset Specification & File Descriptions

### 1. `forces_xyz_raw.mat` (Dynamometer Cutting Forces)
* **Sampling Rate:** $1,000 \text{ Hz}$ ($1 \text{ kHz}$).
* **Sensors:** 3-Axis Piezoelectric Table Dynamometer (Kistler).
* **Format:** MATLAB v7 workspace structure.
* **Fields:** Contains cutting force time-series arrays for each tool cut pass:
  * `Fx`: Feed force ($\text{N}$) - Direction of table movement.
  * `Fy`: Normal force ($\text{N}$) - Perpendicular to table feed.
  * `Fz`: Axial / Thrust force ($\text{N}$) - Parallel to spindle axis (most sensitive indicator of flank wear).
  * $F_{res} = \sqrt{F_x^2 + F_y^2 + F_z^2}$: Instantaneous resultant cutting force.

### 2. `tool/` (Microscope Flank Face Photos)
* **Camera / Fixture:** Industrial Tool Presetter / Optical Microscope.
* **Resolution:** $1550 \times 500 \text{ pixels}$.
* **File Naming Convention:** `T{tool}R{run}B{blade}.jpg`
  * Example: `T10R12B2.jpg` = **Tool #10**, **Cut/Pass Cycle #12**, **Blade/Flute #2**.
* **Ground Truth Features:** Flank wear land ($V_b$), notch wear, burrs, and micro-chipping.

### 3. `labels.csv` & `labels_reg.csv` (Ground Truth Annotations)
* **`labels.csv` (3-Class Categorical):**
  * `SHARP` ($V_b < 70\ \mu\text{m}$): Fresh cutting edge, steady cutting forces.
  * `USED` ($70\ \mu\text{m} \le V_b < 125\ \mu\text{m}$): Moderate flank wear land, elevated friction.
  * `DULLED` ($V_b \ge 125\ \mu\text{m}$ or catastrophic edge failure): ISO 8688-2 tool life criterion reached, spindle halt required.
* **`labels_reg.csv` (Regression Targets):**
  * `flank_wear_um`: Exact physical flank wear land width ($V_b$) measured in micrometers ($\mu\text{m}$).
  * `chipping_gap_um`: Cutting edge irregular gap width ($\mu\text{m}$).
  * `overhang_um`: Built-Up Edge (BUE) overhang width ($\mu\text{m}$).

---

## 🛠️ Verification Script

To verify that your dataset is correctly extracted and readable by the Python backend:

```bash
# Run from repository root
python -c "
import os
import scipy.io as sio
import pandas as pd

dataset_path = 'dataset/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition (1)/Nonastreda Multimodal Dataset for Identifying Tool Wear Condition'
mat_file = os.path.join(dataset_path, 'forces_xyz_raw.mat')
labels_file = os.path.join(dataset_path, 'labels.csv')

print('Verifying Dataset...')
if os.path.exists(mat_file):
    print(f'✅ Found forces_xyz_raw.mat ({os.path.getsize(mat_file) / 1024 / 1024:.1f} MB)')
else:
    print('❌ forces_xyz_raw.mat missing!')

if os.path.exists(labels_file):
    df = pd.read_csv(labels_file)
    print(f'✅ Found labels.csv ({len(df)} records)')
else:
    print('❌ labels.csv missing!')
"
```
