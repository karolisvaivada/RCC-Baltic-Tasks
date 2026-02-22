# Practical Test – Baltic RCC

This repository contains the solution for the **Practical Test Tasks** provided by Baltic RCC.  
It includes data analysis, visualization, and power system model assessment using Python.

---

## Repository Structure

```
.
src/
├── __pycache__/              # Python bytecode cache (ignored in version control)
├── data/                     # Input data and CGMES EQ profile files
│   └── *.xml                 # CGMES model used in Task 2
├── Task_description/         # Original task description and reference material
│   └── Practical_Test_Tasks_RCC.docx
├── functions.py              # Core logic for Task 1 and Task 2
│                              - API data requests (aFRR & imbalance)
│                              - Metric calculations
│                              - Plotting functions
│                              - CGMES XML parsing & validation
└── results.ipynb             # Executed notebook
                               - Data retrieval and visualization (Task 1)
                               - Quantitative assessment and reasoning
                               - CGMES model analysis and answers (Task 2)
```

---

##  Task 1 – aFRR vs System Imbalance Analysis

**Goal:**  
Retrieve data from the Baltic Transparency Dashboard and assess aFRR activation relative to system imbalance for **22.09.2025**.

**Data sources:**
- aFRR activation (`afrr_activation`)
- Total imbalance volumes (`imbalance_volumes_v2`)

**What is done:**
- Data requested via official API (JSON export)
- Time series expanded to uniform resolution
- Plot: |Imbalance| vs aFRR activation
- Quantitative metrics calculated:
  - Total imbalance vs total aFRR
  - Coverage ratio
  - Activation frequency
  - Correlation
  - Peak values

**Key outputs:**
- Interactive Plotly graph
- Metrics table supporting assessment
- Short written reasoning inside the notebook

---

##  Task 2 – CGMES (EQ Profile) Assessment

**Goal:**  
Analyze a provided CGMES EQ XML model and answer power system–related questions.

**What is covered:**
- Total installed generation capacity
- Generator power factor & regulation control
- Transformer winding nominal voltages and type
- Line permanent vs temporary limits
- Slack generator identification
- Detection of semantic, logical, and power-system modeling errors

**Implementation:**
- XML parsed using `lxml`
- CIM structure navigated via XPath
- Results extracted programmatically
- Model issues detected with rule-based checks

---

##  Technologies Used

- Python 3.10+
- pandas
- requests
- plotly
- lxml

---

##  How to Run

1. Install dependencies:
```bash
pip install pandas requests plotly lxml
```

2. Open the notebook:
```bash
jupyter notebook results.ipynb
```

3. All functions are located in `functions.py` and imported into the notebook.

---

##  Notes

- All timestamps are handled in **UTC** to match API output and avoid timezone shifts.
- Code is modular, reusable, and written for clarity and review.
- The notebook contains final answers, plots, and explanations.

---

##  Author

Prepared by **Karolis Vaivada**  
Practical Test – Baltic RCC
