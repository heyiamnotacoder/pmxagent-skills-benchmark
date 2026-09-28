Please perform noncompartmental analysis on the following dataset (nca_benchmark.csv). Please report the following individual and mean PK parameters for each patient/drug: AUC0-last (AUClast), AUC0-infinity observed (AUCINF_obs), terminal half-life(HL_Lambda_z), maximum concentration (Cmax), time to maximum concentration (Tmax), observed systemic clearance (CL_obs or apparent CL/F_obs for extravascular), observed terminal volume of distribution (Vz_obs or apparent Vz/F_obs for extravascular), adjusted R2, and number of terminal timepoints. The final result file should be two CSV files (individual and mean) with the following columns: DRUG, PPTESTCD, PPSTRESN

Notes:
(1) Use adjusted R2 for terminal point selection and lambda_z estimation
(2) Route of administration (ROUTE) of 1 is intravenous and 2 is extravascular
(3) DO NOT perform any unit conversions
(4) Use Linear Up Log Down trapezoidal rule
