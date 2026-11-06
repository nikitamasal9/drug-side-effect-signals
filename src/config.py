"""Shared paths and analysis settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SQL = ROOT / "sql"
OUTPUTS = ROOT / "outputs"
BI_EXPORTS = OUTPUTS / "bi_exports"
DASHBOARD = ROOT / "dashboard"
DB_PATH = PROCESSED / "drug_safety.duckdb"

# --- Disproportionality settings -------------------------------------------
MIN_DRUGS_IN_CLASS = 4      # a class needs at least this many drugs to be tested
MIN_DRUGS_WITH_SE = 3       # a class/side-effect pair needs >= this many drugs in the class with the SE
FDR_ALPHA = 0.05            # Benjamini-Hochberg false discovery rate
MIN_ODDS_RATIO = 2.0        # minimum effect size to call a "signal"

# --- Serious adverse events --------------------------------------------------
# Author-curated list of MedDRA preferred terms treated as "serious" for the
# burden score. Inspired by (not identical to) the EMA Important Medical Event list.
SERIOUS_PTS = {
    "Anaphylactic reaction", "Anaphylactic shock", "Angioedema",
    "Stevens-Johnson syndrome", "Toxic epidermal necrolysis",
    "Drug reaction with eosinophilia and systemic symptoms",
    "Hepatic failure", "Hepatitis fulminant", "Hepatic necrosis", "Acute hepatic failure",
    "Renal failure", "Renal failure acute", "Acute kidney injury",
    "Agranulocytosis", "Aplastic anaemia", "Pancytopenia", "Thrombocytopenia",
    "Neutropenia", "Febrile neutropenia", "Haemolytic anaemia",
    "Torsade de pointes", "Electrocardiogram QT prolonged", "Ventricular fibrillation",
    "Ventricular tachycardia", "Cardiac arrest", "Myocardial infarction", "Cardiac failure",
    "Cardiac failure congestive",
    "Cerebrovascular accident", "Pulmonary embolism", "Deep vein thrombosis",
    "Rhabdomyolysis", "Neuroleptic malignant syndrome", "Serotonin syndrome",
    "Respiratory depression", "Respiratory failure", "Respiratory arrest",
    "Seizure", "Convulsion", "Status epilepticus", "Coma",
    "Suicidal ideation", "Suicide attempt", "Completed suicide",
    "Pancreatitis", "Pancreatitis acute", "Gastrointestinal haemorrhage",
    "Intestinal perforation", "Gastrointestinal perforation",
    "Sepsis", "Septic shock", "Progressive multifocal leukoencephalopathy",
    "Interstitial lung disease", "Pulmonary fibrosis",
    "Tendon rupture", "Lactic acidosis", "Diabetic ketoacidosis", "Hypoglycaemia",
    "Tardive dyskinesia", "Death", "Sudden death",
}

# --- Known class effects used to sanity-check the method ---------------------
# (ATC level-4 code, MedDRA preferred term) pairs that are textbook pharmacology.
KNOWN_CLASS_EFFECTS = [
    ("C10AA", "Rhabdomyolysis", "Statins"),
    ("C10AA", "Myalgia", "Statins"),
    ("C09AA", "Cough", "ACE inhibitors"),
    ("C09AA", "Angioedema", "ACE inhibitors"),
    ("J01MA", "Tendon rupture", "Fluoroquinolones"),
    ("J01MA", "Tendonitis", "Fluoroquinolones"),
    ("N06AB", "Ejaculation disorder", "SSRIs"),
    ("N05AH", "Weight increased", "Atypical antipsychotics (diazepines)"),
    ("N05AD", "Tardive dyskinesia", "Butyrophenone antipsychotics"),
    ("N02AA", "Respiratory depression", "Opioids (natural opium alkaloids)"),
    ("N02AA", "Constipation", "Opioids (natural opium alkaloids)"),
    ("C07AB", "Bradycardia", "Selective beta-blockers"),
    ("H02AB", "Cushingoid", "Glucocorticoids"),
    ("A10BB", "Hypoglycaemia", "Sulfonylureas"),
    ("C03CA", "Hypokalaemia", "Loop diuretics (sulfonamides)"),
    ("M01AE", "Gastrointestinal haemorrhage", "NSAIDs (propionic acid)"),
    ("N03AF", "Hyponatraemia", "Carboxamide anticonvulsants"),
    ("C08CA", "Oedema peripheral", "Dihydropyridine calcium channel blockers"),
]
